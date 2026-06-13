# Skills 参考

> 来源：`AGENTS.md` 四阶段管线中各阶段 Skills 表格

---

## ① 方案设计（需求分析师）

| Skill | 用途 | 适用场景 |
|-------|------|----------|
| `spec-driven-development` | 从零产出结构化需求规格 | 需求模糊、只有一句话描述时先用此 skill 收敛 |
| `interview-me` | 一问一答挖掘真实意图 | 用户提"帮我做 X"但没说清楚为什么、为谁做 |
| `idea-refine` | 发散→收敛，打磨原始想法 | 想法还比较粗糙、需要推敲方案之前 |
| `architecture-blueprint-generator` | 分析代码库生成架构蓝图 | 大型功能涉及多模块改动时，先理清现有架构 |
| `api-and-interface-design` | 设计 API / 模块接口 / 信号契约 | 新增信号/槽、修改 DB schema、跨模块接口 |
| `documentation-and-adrs` | 记录架构决策（ADR） | 涉及取舍的决策（如选方案 A 不选 B），便于回溯 |
| `planning-and-task-breakdown` | 将方案拆解成有序任务列表 | 方案确定后，按分层拆成 TASK-01 ~ TASK-NN |

## ② 评审（审查员）

| Skill | 用途 | 适用场景 |
|-------|------|----------|
| `doubt-driven-development` | 对方案做对抗性审查 | 高风险改动（数据迁移、加密、多线程），在评审时模拟"找茬" |

## ③ 开发与测试（开发 + 测试）

| Skill | 用途 | 适用场景 |
|-------|------|----------|
| `test-driven-development` | 先写测试再编码，红→绿→重构 | **所有逻辑改动**的首选方式，尤其 DB 方法、服务引擎 |
| `incremental-implementation` | 分批提交，每批可验证 | 改动涉及多个文件时，避免一次提交太大 |
| `source-driven-development` | 基于官方文档编码，避免过时模式 | 使用 PyQt6 / openai SDK / python-docx 等第三方 API 时 |
| `frontend-ui-engineering` | 构建生产级 UI | 新增/修改 Qt 窗口、弹窗、组件布局 |
| `code-simplification` | 重构提升可读性，不改行为 | 发现代码臃肿、嵌套深、重复逻辑时 |
| `debugging-and-error-recovery` | 系统化排查根因 | 测试失败、行为不符预期、启动崩溃 |
| `observability-and-instrumentation` | 加日志、埋点，确保可诊断 | 新增关键路径、定时任务、网络调用 |
| `security-and-hardening` | 防注入、加密、输入校验 | 处理用户输入、API Key、文件路径 |
| `performance-optimization` | 性能剖析与优化 | 界面卡顿、大量数据渲染、tick 耗时 |
| `git-workflow-and-versioning` | 规范化 commit/push 流程 | 多分支并行、冲突处理 |

## ④ 代码评审（审查员）

| Skill | 用途 | 适用场景 |
|-------|------|----------|
| `code-review-and-quality` | 多维度代码评审（规范/安全/性能/可维护） | 合并前必须执行 |
| `code-simplification` | 标记可简化的冗余代码 | 评审中发现的过度设计 |
| `shipping-and-launch` | 上线前检查清单、回滚策略 | 大功能合入 main 前 |
