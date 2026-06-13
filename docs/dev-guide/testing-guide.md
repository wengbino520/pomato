# 测试指南

> 来源：`AGENTS.md` 测试规范 + 管线 ③ 3.4 测试规范补充

---

## 运行测试

```bash
# Windows
.venv\Scripts\python -m pytest tests/ -v --tb=short

# Linux
.venv/bin/python -m pytest tests/ -v --tb=short
```

> ⚠️ 必须在 `.venv` 虚拟环境中运行。系统 Python / Conda 环境中的 PyQt6 可能存在 DLL 版本不兼容。

---

## 覆盖维度

| 覆盖类别 | 要求 | 示例 |
|----------|------|------|
| ✅ 正常路径 | 核心功能的主流程能跑通 | `test_add_todo_with_valid_data` |
| 🔲 边界条件 | 空值、最大/最小值、零、负数、超长字符串 | `test_add_todo_empty_title`、`test_max_tags` |
| ⚠️ 异常路径 | 数据库约束冲突、网络失败、文件损坏 | `test_save_invalid_json`、`test_api_timeout` |
| 🔀 组合场景 | 多次操作后的状态、并发弹窗队列 | `test_queue_overflow_replaces_oldest` |
| 🔄 回归验证 | 改动不影响已有 349 用例 | 全量 `pytest` 通过 |

- 边界条件测试**不得省略**——最常见 bug 出在边界
- 新增 DB 方法必须包含 SQL 注入防护测试（参数化查询验证）
- 新增信号/槽必须验证信号发射时序

---

## Fixture 使用

Fixtures 定义在 `tests/conftest.py`：`tmp_config`、`tmp_db`、`engine`、`qapp`（session 级）。

```python
# DB 相关测试 —— 使用 tmp_db fixture（自动隔离到临时目录）
def test_add_todo(tmp_db):
    tid = tmp_db.add_todo("测试待办", priority=2)
    assert tid > 0
    todo = tmp_db.get_todo(tid)
    assert todo["title"] == "测试待办"

# 引擎测试 —— 使用 engine fixture（注入隔离 config）
def test_timer_start(engine):
    assert engine.state == TimerState.IDLE
    engine.manual_start()
    assert engine.state == TimerState.WORK

# Qt 组件测试 —— 使用 qapp fixture，不 show()
def test_popup_signals(qapp, tmp_config):
    popup = PopupWindow(tmp_config, db=None)
    spy = QSignalSpy(popup.submitted)
    popup.submit()
    assert len(spy) == 1
```

---

## Mock 约定

| 场景 | 方式 |
|------|------|
| 隔离数据目录 | `patch("pathlib.Path.home", return_value=tmp_path)` |
| 模拟网络请求 | `patch("src.services.ai_client.AIClient._call_api")` |
| 模拟时间 | `patch("src.services.timer_engine.date")` |
| 禁止 mock | 不 mock `Database` 本身——用 `tmp_db` fixture 操作真实 SQLite |

- 不要在测试中创建真实窗口（`QWidget.show()` 需要桌面环境）
- 信号验证使用 `QSignalSpy`，不手动 sleep
- 文件命名：`tests/test_<module>.py`
