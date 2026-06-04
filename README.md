# 🍅 POMATO — 番茄日志助手

> 自动计时 · 碎片记录 · AI 日报 · 结构化输出

POMATO 是一款 Windows/Linux 桌面端番茄工作法 + AI 日报生成工具。它在工作时段自动启动番茄钟计时，每 25 分钟弹窗提醒你花 30 秒记录刚才做了什么，下班前一键用 AI 生成结构化日报。

---

## 核心特性

| 模块 | 能力 |
|------|------|
| ⏱ **自动计时** | 工作日自动启动，25 分钟工作 / 5 分钟休息循环，每 4 轮长休息 |
| 📝 **弹窗记录** | 到点强制置顶弹窗，文字 + 标签输入，Ctrl+Enter 快捷键提交，支持跳过 |
| 📊 **今日看板** | 当日所有番茄钟时间轴展示，统计已完成数与专注时长，支持编辑/删除/补录 |
| 🤖 **AI 汇总** | 一键将碎片记录发给大模型，生成按项目分类的结构化日报 |
| 📋 **日报输出** | AI 日报可编辑，导出 Markdown / 纯文本，一键复制到剪贴板 |
| 📚 **历史查阅** | 按日期浏览历史日报，支持关键词搜索 |
| ⚙ **灵活配置** | 工作时段、番茄时长、休息时长、AI 接口、自定义标签、开机自启均可配 |
| 🔒 **数据本地** | SQLite 存储，API Key DPAPI 加密，离线可用（仅 AI 汇总需联网） |
| 🖥 **系统托盘** | 最小化到托盘，实时倒计时 tooltip，右键菜单控制暂停/跳过/退出 |

---

## 快速开始

### 环境要求

- Python **3.10+**
- Windows 10/11（主要支持）或 Linux

### 安装

```bash
# 1. 克隆项目
git clone https://github.com/your-org/pomato.git
cd pomato

# 2. 创建虚拟环境
python -m venv .venv

# 3. 安装依赖
# Windows:
.venv\Scripts\pip install -r requirements.txt

# Linux / macOS:
.venv/bin/pip install -r requirements.txt
```

### 启动

```bash
# Windows（双击 run.bat 或命令行）：
run.bat

# Linux / macOS：
chmod +x run.sh && ./run.sh

# 或直接用 Python：
.venv\Scripts\python main.py     # Windows
.venv/bin/python main.py          # Linux
```

> ⚠️ 如安装了 Anaconda，`run.bat` 会自动隔离 Anaconda 的 DLL 冲突，无需额外处理。

### 开发模式（运行测试）

```bash
pip install -r requirements-dev.txt
pytest
```

---

## 使用指南

### 1. 基础工作流

```
08:30 自动启动 ──→ 25 分钟工作 ──→ 弹窗记录（30 秒）──→ 5 分钟休息 ──→ 下一轮
                         ↑                                    │
                         └────────── 循环 4 轮 ───────────────┘
                                    ↓
                              15 分钟长休息 ──→ 继续循环
                                    ↓
                              下班前 ──→ 一键 AI 生成日报 ──→ 编辑并导出
```

### 2. 弹窗记录

番茄钟结束时弹出记录窗口：

- 输入过去 25 分钟做了什么
- 勾选标签（开发 / 测试 / 文档 / 会议…）
- `Ctrl + Enter` 快速提交，窗口自动关闭进入休息
- 点击「跳过本轮」直接进入休息（计入统计）
- 3 分钟未操作，自动标记为"未记录"

### 3. 查看与管理

- **双击托盘图标** 打开主窗口
- 顶部日期选择器 + **◀ ▶ 箭头** 可逐天翻阅历史
- 每条记录可 **✏ 编辑** 或 **🗑 删除**
- 「＋ 手动补录」可补填遗漏的时间段

### 4. AI 日报

点击「📋 生成日报」：

- 全天碎片记录发送给 AI，按项目分类汇总
- 实时流式输出（打字机效果），可中途查看
- **编辑** AI 生成内容后，导出 Markdown 或纯文本
- **一键复制** 直接粘贴到钉钉 / 飞书 / 企业微信
- 不满意可点「🔄 重新生成」

### 5. 历史日报

点击「📚 历史日报」：

- 左侧日期列表，点击查看对应日报
- 搜索框可按 **日期** 或 **内容关键词** 筛选
- 支持复制日报到剪贴板

---

## 配置项

点击托盘菜单「⚙ 设置」或在主窗口顶部进入设置面板：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 工作开始时间 | 08:30 | 每日自动启动计时的时间 |
| 番茄时长 | 25 分钟 | 单个番茄钟持续时长 |
| 短休息时长 | 5 分钟 | 每轮之间的休息时长 |
| 长休息时长 | 15 分钟 | 每 4 轮后的长休息时长 |
| 长休息间隔 | 4 | 触发长休息的番茄钟轮数 |
| 提示音 | 开启 | 弹窗时播放系统提示音 |
| 开机自启动 | 开启 | 系统启动时自动运行 |
| 自定义标签 | 开发/测试/文档/会议/研究/其他 | 弹窗中可选标签，可增删 |
| AI 接口 | OpenAI 兼容 | 支持 OpenAI / 通义千问 / DeepSeek 等 |
| API Key | — | 加密存储于本地 |
| API Base URL | `https://api.openai.com/v1` | 自定义 API 端点 |
| 模型名称 | `gpt-4o-mini` | 使用的模型 ID |
| 日报 Prompt 模板 | 内置默认 | 可自定义 Prompt 控制日报格式 |
| 弹窗超时时间 | 180 秒 | 超时自动标记"未记录" |

> 🔌 **Ollama 本地模型**：设置页面提供一键切换按钮，Base URL 自动设为 `http://localhost:11434/v1`，无需填写 API Key。

---

## 项目结构

```
POMATO/
├── main.py                  # 入口：初始化组件、启动事件循环
├── run.bat / run.sh         # 启动脚本（DLL 隔离 / 虚拟环境检测）
├── requirements.txt         # 生产依赖
├── requirements-dev.txt     # 开发依赖（pytest）
├── pytest.ini               # 测试配置
├── README.md
├── MarkRequirement.md       # 完整需求分析 & 任务追踪
│
├── src/
│   ├── config.py            # 配置管理（JSON 持久化、API Key 加密、开机自启注册表）
│   ├── database.py          # SQLite 数据层（条目 CRUD、日报存取、搜索）
│   ├── timer_engine.py      # 计时引擎（状态机：空闲→工作→短休→长休、暂停/跳过）
│   ├── popup_window.py      # 弹窗记录器（强制置顶、标签选择、Ctrl+Enter 提交、超时处理）
│   ├── main_window.py       # 主窗口 · 今日看板（条目时间轴、编辑/删除/补录、日期导航）
│   ├── report_window.py     # 日报窗口（AI 流式生成、编辑、导出 Markdown/文本、复制）
│   ├── history_window.py    # 历史日报窗口（日期列表、内容预览、关键词搜索）
│   ├── settings_window.py   # 设置面板（所有可配项 UI）
│   ├── ai_client.py         # AI 客户端（OpenAI 兼容接口、Prompt 构建、Ollama 支持）
│   └── tray_manager.py      # 系统托盘管理（菜单、气泡通知、弹窗调度）
│
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_database.py
    ├── test_ai_client.py
    ├── test_timer_engine.py
    └── test_main_window.py
```

---

## 技术栈

| 层次 | 技术 | 说明 |
|------|------|------|
| 框架 | Python + **PyQt6** | 桌面 GUI、系统托盘、弹窗控制 |
| 数据 | **SQLite** | 本地文件数据库，零配置 |
| AI | **openai SDK** | 兼容所有 OpenAI 格式 API（含 Ollama） |
| 托盘 | `QSystemTrayIcon` | 系统托盘图标 + 右键菜单 |
| 加密 | Windows DPAPI | API Key 非明文存储 |
| 打包 | PyInstaller（计划中） | 单文件 .exe 分发 |

---

## 依赖

```
PyQt6 >= 6.4.0, < 6.8.0
openai >= 1.0.0
pywin32 >= 306          (Windows only)
```

---

## 开发进度

| 模块 | 完成度 |
|------|--------|
| 计时引擎 | 90%（节假日检测未实现） |
| 弹窗记录 | 100% |
| 今日看板 | 100% |
| AI 汇总 | 100% |
| 日报导出 | 86%（Word/PDF 未实现） |
| 配置中心 | 100% |

> 详细任务追踪见 [`MarkRequirement.md`](MarkRequirement.md)

---

## License

MIT


