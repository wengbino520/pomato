# 多 Profile 资料空间方案（标准流程 · 设计文档）

> 创建时间: 2026-07-04
> 状态: 方案设计 / 待用户确认
> 范围: 门禁 1 - 设计文档
> 目标: 解决测试数据、真实数据、实验数据混用问题，同时为后续真正多用户留出演进空间

---

## 1. 背景

当前 POMATO 的本地数据目录固定为 `Path.home() / ".pomato"`，核心文件直接写在同一个根目录下：

- `config.json`
- `pomato.db`
- `holiday_cache.json`
- `logs/pomato.log`
- `backups/pomato_YYYY-MM-DD.db`

这在单人、单环境、长期稳定使用时足够简单，但已经暴露出新的真实痛点：

1. 开发/测试数据与真实工作数据混在一起。
2. 用户想试验新功能时，不敢在真实资料库上直接操作。
3. AI 汇总、日记、待办、提醒、历史报告都共用同一份数据库，误操作影响面越来越大。
4. 当前代码把数据根目录分散写在 `Config`、`Database`、`logger` 等模块中，后续扩展会越来越难。

因此，当前阶段最值得做的不是“完整多用户系统”，而是“单机多 Profile 资料空间”。

---

## 2. 设计结论

### 2.1 选择方案

本阶段选择：**多 Profile / 多资料空间**。

定义：
- 一个 Windows 登录用户下，可以拥有多个彼此隔离的 POMATO 资料空间。
- 每个 Profile 拥有独立配置、数据库、节假日缓存、日志和备份。
- 用户可在“真实工作”“开发测试”“实验环境”等资料空间间切换。

### 2.2 明确不做的内容

本阶段不做：
- 账号系统
- 登录/密码/权限管理
- 云端同步
- 多设备共享同一资料空间
- 运行时热切换整套内存状态

### 2.3 为什么不直接做“多用户”

“多用户”会引入新的系统级复杂度：
- 用户身份认证
- 权限边界
- 各用户独立密钥与配置策略
- 更复杂的数据迁移与故障恢复

但用户当前最强烈的痛点其实是“资料隔离”，不是“身份管理”。

所以本轮聚焦：

> 先解决数据隔离问题，再决定未来是否值得升级到真正的多用户系统。

---

## 3. 设计目标

### 3.1 核心目标

1. 让真实数据、测试数据、实验数据彻底隔离。
2. 保持现有单机产品的使用心智，不引入重型登录流程。
3. 尽量少改现有业务逻辑，优先抽象“数据路径”而不是重写功能。
4. 保证旧用户升级后数据不丢失。
5. 为后续日记长期分析、未来推演等高价值数据能力提供更稳固的资料边界。

### 3.2 成功标准

当以下条件全部满足时，可认为该方案完成：

1. 用户可以创建至少 2 个互相隔离的 Profile。
2. 每个 Profile 的番茄、日记、待办、提醒、报告数据完全独立。
3. 用户切换 Profile 后，不会看到前一个 Profile 的数据。
4. 旧版单目录用户升级后，历史数据可自动迁移或自动接管，且无丢失。
5. 测试代码与手动测试流程可以显式指定资料空间，而不污染真实数据。
6. 切换行为可预测、可恢复，失败时不会破坏原资料。

---

## 4. 需求边界

### 4.1 本阶段范围

- Profile 注册表
- 当前激活 Profile 持久化
- Profile 创建
- Profile 切换
- Profile 重命名
- 基于 Profile 的独立数据目录
- 旧数据迁移或接管策略
- 启动参数/测试参数支持
- 最小可用 UI 入口

### 4.2 延后范围

- Profile 删除
- Profile 导出/导入
- Profile 云备份
- Profile 图标/颜色个性化
- Profile 间数据合并
- Profile 粒度的 AI 模型配置差异分析页

### 4.3 非目标

- 不提供系统级权限隔离
- 不承诺不同 Windows 用户之间共享资料
- 不做多人协作
- 不在本阶段引入新第三方依赖

---

## 5. 用户场景

### 场景 A：真实工作与开发测试分离

- 用户已有长期真实工作数据。
- 用户想验证新功能或调试数据库。
- 用户创建 `dev-test` Profile。
- 之后所有开发演练在 `dev-test` 中进行，不再污染真实工作资料。

### 场景 B：实验新流程

- 用户想尝试新的标签体系、AI 提示词或新的记录习惯。
- 用户创建 `experiment-q3` Profile。
- 经过一段时间验证，再决定是否迁回主 Profile。

### 场景 C：升级老版本

- 用户此前一直只有默认目录 `~/.pomato/`。
- 升级后系统自动建立默认 Profile。
- 用户几乎无感继续使用，不需要重新配置。

---

## 6. 交互方案

### 6.1 设计原则

1. 默认简单：只有一个 Profile 时，不打扰用户。
2. 切换明确：切换是重要操作，必须让用户知道自己进入了哪个资料空间。
3. 降低实现风险：本阶段切换后通过“重启应用”生效，不做运行时热切换。

### 6.2 入口设计

建议提供两个入口：

1. 托盘菜单新增：`切换资料空间...`
2. 设置窗口新增：`资料空间` 分组

### 6.3 首阶段 UI 方案

#### 方案 A：设置页管理 + 切换后重启生效

设置页新增一块资料空间面板：

- 当前资料空间：`main`
- 资料空间列表
- `新建资料空间`
- `重命名`
- `切换并重启`

优点：
- 改动最小
- 最符合当前桌面应用结构
- 不需要在应用启动前增加复杂窗口

结论：**本阶段采用方案 A。**

### 6.4 切换流程

1. 用户点击 `切换资料空间...`
2. 弹出资料空间管理对话框
3. 选择目标 Profile
4. 系统保存新的 `active_profile_id`
5. 提示“切换将在应用重启后生效”
6. 用户确认后，应用自动退出并重新启动

### 6.5 为什么不做热切换

如果运行时热切换，需要同时重建：
- `Config`
- `Database`
- `ReminderEngine`
- `TimerEngine`
- `MainWindow`
- 托盘状态
- 所有已打开窗口与未保存上下文

这会显著提高出错概率，尤其当前已存在：
- 自动计时状态
- 弹窗队列
- 日记页未保存状态
- 报告窗口与历史窗口

因此本阶段明确采用：

> 切换资料空间 = 持久化目标 Profile + 重启后生效。

这能把复杂度压在可控范围内。

---

## 7. 数据目录与文件布局

### 7.1 目标目录结构

```text
~/.pomato/
├── profiles.json
├── profile_state.json
├── profiles/
│   ├── main/
│   │   ├── config.json
│   │   ├── pomato.db
│   │   ├── holiday_cache.json
│   │   ├── logs/
│   │   │   └── pomato.log
│   │   └── backups/
│   ├── dev-test/
│   │   ├── config.json
│   │   ├── pomato.db
│   │   ├── holiday_cache.json
│   │   ├── logs/
│   │   └── backups/
│   └── experiment-q3/
└── migrations/
    └── profile-bootstrap-*.json
```

### 7.2 全局文件与 Profile 文件职责

全局文件：
- `profiles.json`：资料空间注册表
- `profile_state.json`：当前激活的 Profile
- `migrations/`：迁移记录，便于诊断和回滚

Profile 内文件：
- `config.json`：该资料空间独立配置
- `pomato.db`：该资料空间独立数据库
- `holiday_cache.json`：该资料空间节假日缓存
- `logs/`：该资料空间日志
- `backups/`：该资料空间数据库备份

### 7.3 注册表示例

```json
{
  "version": 1,
  "profiles": [
    {
      "id": "main",
      "name": "主资料空间",
      "created_at": "2026-07-04T10:30:00",
      "is_default": true
    },
    {
      "id": "dev-test",
      "name": "开发测试",
      "created_at": "2026-07-04T10:45:00",
      "is_default": false
    }
  ]
}
```

### 7.4 当前激活状态示例

```json
{
  "active_profile_id": "main",
  "updated_at": "2026-07-04T10:45:00"
}
```

---

## 8. 技术方案

### 8.1 核心思路

引入“路径解析”作为新基础设施层，把当前散落在多个模块里的 `Path.home() / ".pomato"` 统一收口。

### 8.2 新增基础设施组件

建议新增：`src/core/profile_manager.py`

职责：
- 定位全局应用根目录
- 管理 `profiles.json`
- 管理 `profile_state.json`
- 创建/列出/重命名 Profile
- 解析当前激活 Profile 的数据目录
- 执行首次迁移/接管逻辑

可考虑拆出值对象：`AppPaths` 或 `ProfilePaths`

职责：
- `app_root`
- `profiles_root`
- `profile_dir`
- `config_file`
- `db_file`
- `holiday_cache_file`
- `log_dir`
- `backup_dir`

### 8.3 对现有模块的改造方向

#### `main.py`

新增启动期解析：
- `--profile <id>`
- `--data-dir <path>`（开发/自动化测试优先）

启动顺序建议改为：

1. 解析命令行参数
2. 初始化 `ProfileManager`
3. 决定当前 Profile 数据目录
4. 用该目录初始化日志
5. 用该目录构造 `Config` 与 `Database`
6. 再启动 `ReminderEngine`、`TimerEngine`、`TrayManager`

#### `src/core/config.py`

当前问题：内部自己决定 `Path.home() / ".pomato"`。

建议改造：
- `Config(data_dir: Path | None = None)`
- 若未传入，则保持兼容默认行为
- 若传入，则严格使用指定目录

#### `src/core/database.py`

建议改造：
- `Database(data_dir: Path | None = None)`
- 数据库路径、备份路径均由 `data_dir` 派生

#### `src/services/logger.py`

建议改造：
- `setup_logging(log_dir: str | Path = "", *, console: bool = False)` 继续保留
- 但 `main.py` 应显式传入当前 Profile 的 `log_dir`
- 避免日志继续写入全局 `~/.pomato/logs/`

#### `src/services/holiday_manager.py`

当前已支持外部传入 `data_dir`，这一点可以复用。

#### `src/ui/settings_window.py`

新增资料空间管理入口：
- 显示当前资料空间名称与路径
- 新建资料空间
- 重命名资料空间
- 切换资料空间
- 新建时复制当前激活 Profile 的安全配置子集作为初始配置
- `api_key` 不继承，避免敏感信息泄漏
- `autostart_enabled` 重置为 `False`，避免多个 Profile 争抢应用级自启动状态

#### `src/app.py`

托盘菜单新增资料空间入口：
- `切换资料空间...`

### 8.4 与现有架构的关系

该方案符合当前四层架构：

- L1 `core/`: 新增 ProfileManager，扩展 Config/Database
- L2 `services/`: logger 使用外部注入路径
- L3 `ui/`: 设置页/对话框新增资料空间管理 UI
- L4 `app.py`: 托盘菜单集成 + 重启切换编排

---

## 9. 迁移策略

### 9.1 迁移目标

让老用户从“单目录模式”平滑升级到“Profile 模式”。

### 9.2 建议策略

采用：**一次性 bootstrap 到默认 Profile**。

规则：

1. 如果 `profiles.json` 不存在，且旧目录中存在 `config.json` 或 `pomato.db`，则视为旧版本升级。
2. 系统自动创建默认 Profile：`main`。
3. 将旧目录中的核心数据文件迁移到 `profiles/main/`。
4. 生成迁移记录文件，写入迁移时间与迁移结果。
5. 迁移完成后，写入 `profile_state.json`，将 `main` 设为激活 Profile。

### 9.3 迁移安全策略

迁移时必须满足：

1. 先创建目标目录。
2. 先复制，再校验，再重命名原文件为备份，避免直接覆盖。
3. 任一步失败时，不切换 `active_profile_id`。
4. 迁移过程必须记录日志。

### 9.4 为什么不长期保留“根目录就是默认 Profile”

虽然这样能减少一次迁移，但长期会导致：
- 默认 Profile 成为特殊分支
- 代码里充满条件判断
- 测试和维护复杂度上升

因此更推荐统一结构：

> 所有 Profile 都在 `profiles/<id>/` 下，默认 Profile 也不例外。

---

## 10. 测试与开发支持方案

### 10.1 对测试场景的直接支持

为了解决“测试污染真实数据”，本方案要求支持显式资料目录注入。

优先级建议：

1. `--data-dir <path>`：自动化测试/手工调试最强控制方式
2. `--profile <id>`：在已注册 Profile 中快速切换
3. `profile_state.json`：普通用户默认启动路径

补充约束：

- 测试优先使用显式 `app_root` / `data_dir`，而不是仅依赖 `Path.home()` patch
- 根级 `profiles.json` / `profile_state.json` 在测试中也必须落入隔离目录，避免污染真实资料空间

### 10.2 建议命令

```bash
# Windows - 真实使用
.venv\Scripts\python main.py

# Windows - 指定 Profile 启动
.venv\Scripts\python main.py --profile dev-test

# Windows - 指定独立资料目录启动（开发/调试）
.venv\Scripts\python main.py --data-dir D:\temp\pomato-sandbox

# 全量测试
.venv\Scripts\python -m pytest tests/ -v --tb=short

# 仅跑配置/数据库测试
.venv\Scripts\python -m pytest tests/test_config.py tests/test_database.py -v --tb=short
```

### 10.3 测试策略

新增测试应覆盖：

1. `ProfileManager` 初始化与注册表读写
2. 创建 Profile 时目录结构是否完整
3. 重命名 Profile 是否同步更新注册表
4. 切换 Profile 是否正确更新 `profile_state.json`
5. `Config(data_dir=...)` 是否写到指定目录
6. `Database(data_dir=...)` 是否写到指定目录
7. 旧目录迁移是否成功，失败是否安全回退
8. UI 管理对话框的关键操作链路
9. `--profile` / `--data-dir` 启动参数解析

---

## 11. 风险与权衡

### 风险 1：迁移误伤真实数据

缓解：
- 先复制后切换
- 保留迁移记录
- 失败不写激活状态
- 首次实现必须有迁移测试

### 风险 2：切换时状态未清理干净

缓解：
- 本阶段不做热切换
- 强制走“切换后重启”

### 风险 3：路径注入遗漏，导致仍写入旧目录

缓解：
- 对 `Config`、`Database`、`logger`、`HolidayManager` 做统一排查
- 增加针对文件落点的测试
- 用搜索检查 `Path.home() / ".pomato"` 残留点

### 风险 4：Profile 名称与目录 id 混淆

缓解：
- 内部稳定标识使用 `id`
- UI 展示使用 `name`
- 重命名只改 `name`，目录 `id` 是否允许变更由实现阶段再定

### 风险 5：范围蔓延成“多用户系统”

缓解：
- 明确本阶段目标是资料隔离，不做身份系统
- 所有任务围绕“独立资料目录”闭环展开

### 风险 6：应用级自启动与 Profile 级配置冲突

缓解：
- 首版新建 Profile 时不继承 `autostart_enabled`
- 自启动视为应用级行为，不默认跟随 Profile 复制
- 后续在 `TASK-07` / `TASK-10` 中进一步明确切换时的注册表策略

---

## 12. 代码边界

### Always

- 优先抽象统一的数据路径入口，避免继续散写 `Path.home()`
- 保持 `Config`、`Database` 默认构造兼容旧调用点
- 所有迁移都要可记录、可回退、可测试
- 数据库操作继续使用现有 `Database` 封装与参数化查询

### Ask First

- 是否允许真正删除 Profile 及其目录
- 是否允许重命名时同步更改目录 `id`

### Never

- 不直接覆盖旧用户数据文件
- 不在没有迁移测试的前提下改写默认数据目录逻辑
- 不把热切换和资料隔离一起做进首版
- 不引入账号密码或云同步复杂度

---

## 13. 影响范围

预估影响模块：

- `main.py`
- `src/core/config.py`
- `src/core/database.py`
- `src/core/profile_manager.py`（新增）
- `src/services/logger.py`
- `src/ui/settings_window.py`
- `src/app.py`
- 可能新增 `src/ui/profile_manager_dialog.py`
- `tests/test_config.py`
- `tests/test_database.py`
- 新增 `tests/test_profile_manager.py`
- UI 相关测试文件

这是一次 **L1 基础设施先行、再向上层透出 UI** 的改动。

---

## 14. 方案取舍总结

### 选中的方案

- 方案：单机多 Profile
- 默认 Profile 名称：`主资料空间`
- 切换模式：切换后自动重启生效
- 目录模式：统一使用 `profiles/<id>/`
- 新建行为：复制当前激活 Profile 的安全配置子集作为初始配置
- Profile 命名：首版限制名称格式，避免非法字符与歧义命名
- 测试支持：增加 `--profile` 与 `--data-dir`

### 没选的方案

- 真正多用户：复杂度过高，不是当前核心痛点
- 热切换：状态清理复杂，容易出错
- 默认 Profile 继续留在根目录：长期维护成本过高

---

## 15. 已确认决策

1. 默认 Profile 的用户可见名称确定为“主资料空间”。
2. Profile 切换后采用“自动退出并重启”。
3. 新建 Profile 时复制当前激活 Profile 的安全配置子集作为初始配置；`api_key` 不继承，`autostart_enabled` 置为 `False`。
4. 首版限制 Profile 名称格式，避免非法字符、空名称和歧义命名。

### 15.1 Profile 名称规则

首版名称规则建议如下：

- 长度 1-32 个字符
- 允许中文、英文、数字、空格、短横线 `-`、下划线 `_`
- 不允许前后空格
- 不允许纯空白名称
- 不允许与已有 Profile 名称重名
- 内部目录 `id` 由系统生成，不直接使用展示名称

---

## 16. 结论

这不是一个“功能按钮”级改动，而是一次值得尽早完成的数据边界重构。

如果日记、长期分析、未来推演要继续演进，资料空间隔离越晚做，未来迁移成本越高。

因此建议：

> 先以“多 Profile 资料空间”完成数据边界抽象，再继续推进更高阶的 AI 长期陪伴能力。
