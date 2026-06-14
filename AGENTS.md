# POMATO 项目开发指引 (for AI Agents)

> 自动计时 · 碎片记录 · AI 日报 · 结构化输出
> Python 3.10+ · PyQt6 (6.4-6.8) · SQLite · pytest

---

## 项目结构

四层架构：`main.py`（入口）→ `src/core/`（L1 基础设施）→ `src/services/`（L2 业务逻辑）→ `src/ui/`（L3 展示），由 `src/app.py`（L4 编排）串联。

**依赖流向**：`Config` + `Database` → `TimerEngine` + `ReminderEngine` → `TrayManager` → UI 窗口

> 📖 当前完整文件清单、模块职责说明 → **`README.md`**（随代码演进保持最新）

---

## 代码规范

### 日志
```python
from src.services.logger import get_logger
logger = get_logger(__name__)
```
- 每个模块用 `get_logger(__name__)`，禁止 `logging.getLogger()`。`logger.info()` 关键事件、`logger.debug()` 诊断、`logger.exception()` 捕获异常
- **严禁** `except: pass` 空吞异常，至少 `logger.debug(...)` 记录

### 数据库
- **必须参数化查询**，禁止 f-string 拼接 SQL。所有 DB 操作通过 `src/core/database.py`，不创建临时连接
- `_get_conn()` 返回 `sqlite3.Connection`，`row_factory = sqlite3.Row`
- Migration 写法：`try: ALTER TABLE ... except: logger.debug("Migration: ...")`
- 数据目录：`Path.home() / ".pomato"`，测试中用 `patch("pathlib.Path.home", ...)` 隔离

### 配置
- 默认值集中在 `DEFAULT_CONFIG` 字典。API Key 存储：Windows DPAPI 加密 / Linux XOR 混淆
- 读写：`config.get(key)` / `config.set(key, value)`，设置窗口调用 `config.save()`

### Qt 模式
- **信号/槽通信**，禁止跨模块直接方法调用
- 托盘：`QSystemTrayIcon` + `QMenu`，`setQuitOnLastWindowClosed(False)` 保持后台
- 弹窗：`WindowStaysOnTopHint | Dialog`，`setModal(False)`
- **单一 `QTimer(1000ms)`** 驱动 `TimerEngine._on_tick()` + `ReminderEngine.on_tick()`，零额外线程

### 导入路径
```python
# ✅ 正确
from src.core.config import Config
from src.services.timer_engine import TimerEngine
from src.services.logger import get_logger

# ❌ 错误 — 相对导入在测试中会失败
from .config import Config
```

### Git
- 分支：`main` → `origin`。Commit：`feat:` / `fix:` / `refactor:` / `test:` + 中文描述
- 任务类 commit 以 `TASK-NN` 结尾。提交前跑全量测试

---

## Windows 特别规则

- `main.py` 头部 DLL 预加载块（1-30 行）**不可删除、不可调序**
- `pywin32>=306` 用于注册表自动启动。DPAPI 调用必须 `if sys.platform == "win32"` 守卫
- `run.bat` 隔离 Anaconda PATH 避免 DLL 冲突，`build.bat` 用 PyInstaller 打包 `.exe`

---

## 构建与测试

```bash
.venv\Scripts\python -m pytest tests/ -v --tb=short   # Windows
.venv/bin/python -m pytest tests/ -v --tb=short        # Linux
.venv\Scripts\python main.py                            # 运行应用
```

> ⚠️ 必须在 `.venv` 虚拟环境中运行。系统 Python / Conda 中的 PyQt6 可能存在 DLL 不兼容。
> 基准：**全部用例通过，0 regression**（运行 `pytest tests/ -v` 确认）。

Fixtures（`tests/conftest.py`）：`tmp_config`、`tmp_db`、`engine`、`qapp`（session 级）。
详细测试约定（覆盖维度、Fixture 示例、Mock 规则）→ `docs/dev-guide/testing-guide.md`

---

## 约束清单

| 禁止 | 替代方案 | 为什么 |
|------|----------|--------|
| 引入新线程 | 复用 1s QTimer tick | Qt 非线程安全，单 tick 避免竞态 |
| 擅自加依赖 | 当前仅 PyQt6 / openai / pywin32 / python-docx | 保持 `.exe` 体积可控，减少 DLL 冲突风险 |
| 修改 main.py DLL 块 | 固定不动 | Anaconda vcruntime140 版本冲突会静默崩溃 |
| 相对导入 `from .xxx` | `from src.xxx` | 测试中相对导入解析路径不可靠 |
| SQL 字符串拼接 | 参数化查询 | SQL 注入 + 引号转义隐患 |
| `except: pass` | `logger.debug(...)` 或 `logger.exception(...)` | 静默吞异常是 bug 温床，无法回溯 |
| 未跑测试就提交 | `.venv` 中 `pytest tests/` 确认通过 | Schema 变更、重构可能悄悄破坏查询 |
| 在系统 Python/Conda 中跑测试 | 使用 `.venv` 虚拟环境 | Conda PyQt6 DLL 版本不兼容，测试会假失败 |
| 无设计直接编码 | 先写 `docs/design/` 方案，评审通过再开工 | 无设计 = 返工，频繁推翻会污染整个代码库 |
| 跳过代码评审合入 | 开发完成后必须 CR | 单人盲区不可避免，二次审查是最后防线 |
| 测试只写正常路径 | 边界条件、异常路径必须覆盖 | 正常路径只证明"理想情况"，边界才是 bug 来源 |

---

## 新增模块 Checklist

新增 `src/services/` 或 `src/ui/` 模块时，按以下清单逐项完成：

- [ ] 用 `get_logger(__name__)` 初始化日志
- [ ] 用 `from src.xxx import ...` 绝对导入
- [ ] 如有新增跨层信号，登记到上方**信号/槽契约表**
- [ ] 在 `tests/` 下创建同名 `test_xxx.py`（至少覆盖正常路径 + 2 个边界 + 1 个异常路径）
- [ ] 如需隔离 fixture，在 `tests/conftest.py` 中注册
- [ ] 更新 `README.md` 模块状态表（如涉及新功能）
- [ ] 运行 `pytest tests/ -v` 确认 0 regression

---

## 🔔 Skills 使用提醒

**进入任何开发阶段前，先查阅 `docs/dev-guide/skills-reference.md` 选择适合的 Skill。** 每个阶段都有对应的 Skill 可辅助——方案设计用 `spec-driven-development`/`interview-me`，评审用 `doubt-driven-development`，开发用 `test-driven-development`/`incremental-implementation`，代码评审用 `code-review-and-quality`。

**开发新功能前，先读 `docs/evolution-roadmap.md`** 了解当前项目阶段、已完成功能和已知缺口。

---

## 开发流程（四阶段管线 · 门禁确认制）

```
┌──────────────────────────────────────────────────────────────────────┐
│ ① 方案设计 (🎯 需求分析师)                                            │
│  设计文档 ──→ 🚪【用户确认】──→ 用户故事 ──→ 🚪【用户确认】              │
│  ──→ TASK 拆分 ──→ 🚪【用户确认】                                     │
└──────────────────────────────────┬───────────────────────────────────┘
                                   ↓ 确认通过
┌──────────────┐     ┌───────────────┐     ┌────────────┐
│ ② 技术评审    │ ──→ │ ③ 开发测试     │ ──→ │ ④ 代码评审  │
│ 🔍 审查员     │    │ 💻 开发+🧪测试 │     │ 🔎 审查员   │
└──────────────┘     └───────┬───────┘     └──────┬─────┘
                             │                    ↓
                             └──── 🚪【用户确认合并】──→ main
```

> ⚠️ **门禁规则**：每个 🚪 标记处 **必须暂停**，等待用户明确确认后方可继续。用户可能提出修改意见，需迭代完善直到用户认可。

---

### ① 方案设计（含三道确认门禁）

**角色**：🎯 需求分析师。将模糊需求逐步转化为设计文档 → 用户故事 → 任务清单，每步均需用户确认。

**前置**：先读 `docs/evolution-roadmap.md` 了解当前项目阶段与已知缺口。

**步骤 1 — 设计文档**：分析需求，输出 `docs/design/YYYY-MM-DD-<feature>.md`（含背景、目标、技术方案、影响范围、风险权衡）。

> 🚪 **门禁 1**：提交设计文档后 **等待用户确认**。收集反馈，修改设计，直到用户同意进入下一步。

**步骤 2 — 用户故事**：基于确认的设计，按 `docs/dev-guide/user-story-template.md` 模板拆解用户故事（含 Given/When/Then 验收标准、P0/P1/P2 优先级）。

> 🚪 **门禁 2**：提交用户故事后 **等待用户确认**。调整优先级、补全场景、修正验收条件，直到用户认可。

**步骤 3 — TASK 拆分**：基于确认的用户故事，按 `docs/dev-guide/task-template.md` 模板拆解为有序 TASK 清单（含依赖关系、检查点 CP、预估影响文件）。

> 🚪 **门禁 3**：提交 TASK 清单后 **等待用户确认**。调整粒度、修正顺序、补充遗漏，直到用户同意进入开发。

**模板参考**：
- 用户故事模板 → `docs/dev-guide/user-story-template.md`
- 任务清单模板 → `docs/dev-guide/task-template.md`

### ② 技术评审（通过方可开发）

**角色**：🔍 审查员。对已确认的设计方案做对抗性技术审查：架构分层合规、依赖影响可控、测试策略充分、TASK 拆解合理。未经评审不得编码。

> 此阶段为 AI 内部审查，无需用户介入（用户已在 ① 中确认内容）。

### ③ 开发与测试（断点续传）

**角色**：💻 开发 + 🧪 测试。先写测试 → 再写实现 → 跑测试 → 重构。按 TASK 依赖顺序逐层推进。

**每完成一个 TASK**：
```
1. git commit -m "<类型>: <描述> TASK-NN"
2. 更新任务清单：标记 TASK-NN 为 ✅ 已完成
3. 检查是否到达检查点（CP），标记检查点完成
```

**信号/槽契约**（跨模块通信唯一方式，新增信号必须登记）：

| 信号来源 | 信号签名 | 接收者 | 用途 |
|----------|----------|--------|------|
| `TimerEngine.work_session_ended` | `(int, str, str)` → session_no, start, end | `TrayManager._show_popup` | 番茄结束弹窗 |
| `TimerEngine.break_ended` | `(bool)` → is_long_break | `TrayManager._on_break_ended` | 休息结束通知 |
| `TimerEngine.tick` | `(int, str)` → remaining, state | `TrayManager._update_tooltip` | 托盘倒计时 |
| `ReminderEngine.reminder_triggered` | `(int, str, str)` → rid, title, time | `TrayManager._on_reminder_triggered` | 提醒弹窗 |
| `ReminderEngine.todos_changed` | `()` | `TodoListWidget.refresh` | 待办列表刷新 |
| `TimerEngine.state_changed` | `(str)` → state_label | `TrayManager._on_state_changed` | 状态变更（托盘图标/菜单同步） |

> 📌 **登记规则**：仅登记**跨层信号**（`services/` → `ui/` 或 `services/` → `app.py`）。UI 内部信号（如 `PopupWindow.submitted`）和同层信号无需登记。

**错误处理模式**：

| 模式 | 写法 | 适用 |
|------|------|------|
| 记录 + 降级 | `except SpecificError: logger.warning(...); result = fallback` | 可恢复错误 |
| 记录 + 上抛 | `except FatalError: logger.exception(...); raise` | 严重错误 |
| ❌ 静默吞异常 | `except: pass` — **禁止**，至少 `logger.debug(...)` | — |

**`__init__.py` 约定**：所有 `src/` 下的 `__init__.py` **不做 re-export**（可包含模块级 docstring 或注释，但不得包含 `import` 语句或 `__all__`）。

### ④ 代码评审

**角色**：🔎 审查员。检查代码规范、日志完整、异常处理、性能影响、测试覆盖率。

> 🚪 **门禁 4**：评审通过后，**等待用户确认**是否合并到 `main`。用户可能要求补充测试、调整实现细节后再合并。

---

## 常见故障排查

| 症状 | 诊断命令 | 常见原因 |
|------|----------|----------|
| `ImportError: PyQt6` | `.venv\Scripts\pip list \| findstr PyQt6` | 未在 `.venv` 中安装 |
| DLL load failed (error 126) | 检查是否在 Conda 环境中运行 | Anaconda DLL 优先级冲突，用 `run.bat` 启动 |
| `pytest` 0 collected | `python -c "import src"` | `sys.path` 未包含项目根目录 |
| `ModuleNotFoundError: src.xxx` | `echo %PYTHONPATH%` | 未从项目根目录运行 |
| `sqlite3.OperationalError: no such table` | 检查 `~/.pomato/pomato.db` | `_init_db()` 未执行或数据目录权限问题 |
| UI 卡死 / 无响应 | 排查 tick 耗时（`logger.debug` 打点） | QTimer 回调中有阻塞操作（网络/文件 I/O） |
| 托盘图标不显示 | `Get-Location` 确认运行目录 | 图标文件路径分辨率，或 DE 不支持托盘 |

> 💡 排查黄金法则：**先确认是否在 `.venv` 中运行** — 80% 的问题源于环境错误。


