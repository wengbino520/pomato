# 多 Profile 资料空间 — 开发任务清单（依赖排序 · 可断点续传）

> 创建时间: 2026-07-04
> 基于: [2026-07-04-profile-workspace.md](2026-07-04-profile-workspace.md), [2026-07-04-profile-workspace-user-stories.md](2026-07-04-profile-workspace-user-stories.md)
> 当前范围: 首版仅覆盖多 Profile 资料隔离、迁移、切换重启、开发测试显式目录注入
> 总预估: 2.5 ~ 4 天（12 个 TASK + 4 个检查点）
> Commit 约定: 每个 TASK 完成后单独提交，commit 标题以 `TASK-NN` 结尾

---

## 范围说明

本轮首版只解决“资料隔离”闭环，不扩展为真正多用户系统。

当前进入开发范围的用户故事：

- `US-01` 老用户无感升级到默认资料空间
- `US-02` 创建独立资料空间
- `US-03` 限制 Profile 名称格式
- `US-04` 切换资料空间并自动重启
- `US-05` 在设置页和托盘中管理资料空间
- `US-06` 重命名资料空间
- `US-07` 开发和测试显式指定隔离目录
- `US-08` 资料空间间数据彻底隔离
- `US-09` 资料空间失败场景可恢复

本轮明确不进入开发范围：

- Profile 删除
- 导出 / 导入
- 云同步
- 多设备共享
- 运行时热切换
- 账号与权限系统

---

## 技术评审约束（开发时必须遵守）

- 资料目录解析必须统一收口，禁止继续在新增代码里直接散写 `Path.home() / ".pomato"`。
- `Config` 与 `Database` 需要保留默认构造兼容性，避免一次性打爆现有调用点和测试。
- Profile 名称用于 UI 展示，内部稳定标识使用单独生成的目录 `id`，不要直接把展示名作为路径名。
- 迁移必须遵循“先复制、校验、记录，再切换激活状态”的顺序，失败时不能覆盖旧数据。
- 切换资料空间首版必须走“保存状态后自动重启”，禁止在同一进程内热切换 `Config` / `Database` / `TimerEngine` / `MainWindow`。
- `--data-dir` 优先级高于 `--profile` 与默认激活状态，便于测试和沙箱调试。
- 每个 TASK 完成后必须有最小验证，不允许把所有测试堆到最后一次性补。

---

## 第一层：L1 基础设施与路径抽象

### TASK-01: 新增 `profile_manager.py` 与路径值对象骨架
- **状态**: ✅ 已完成
- **依赖**: 无
- **文件**: `src/core/profile_manager.py`, `tests/test_profile_manager.py`
- **操作**:
  1. 新增 `ProfileManager`，负责应用根目录、Profile 根目录、状态文件和注册表文件定位
  2. 设计 `ProfilePaths` 或等价值对象，统一暴露 `profile_dir / config_file / db_file / holiday_cache_file / log_dir / backup_dir`
  3. 提供默认应用根目录解析逻辑，兼容当前 `~/.pomato/`
  4. 保持实现不直接耦合 UI
- **验证**:
  - 可解析默认应用根目录
  - 可返回默认 Profile 目录结构
  - 测试中可传入临时根目录构造实例
- **对应 US**: `US-07`, `US-08`
- **预计**: 45 分钟

### TASK-02: `ProfileManager` — 注册表与激活状态读写
- **状态**: ✅ 已完成
- **依赖**: TASK-01
- **文件**: `src/core/profile_manager.py`, `tests/test_profile_manager.py`
- **操作**:
  1. 实现 `profiles.json` 与 `profile_state.json` 的读写
  2. 支持列出 Profile、读取激活 Profile、设置激活 Profile
  3. 约定默认 Profile `id = main`，显示名默认为“主资料空间”
  4. 保证文件不存在时可自动初始化默认结构
- **验证**:
  - 首次初始化时自动创建默认 Profile 元数据
  - 可读取和修改 `active_profile_id`
  - 重复初始化不产生重复 Profile
- **对应 US**: `US-01`, `US-04`
- **预计**: 45 分钟

### TASK-03: `ProfileManager` — Profile 名称校验与 `id` 生成规则
- **状态**: ✅ 已完成
- **依赖**: TASK-02
- **文件**: `src/core/profile_manager.py`, `tests/test_profile_manager.py`
- **操作**:
  1. 实现名称校验：长度、空白、非法字符、重名检查
  2. 将展示名与内部目录 `id` 解耦，系统自动生成稳定 `id`
  3. 明确首版重命名只修改显示名，不修改目录 `id`
  4. 输出统一错误信息，便于 UI 直接展示
- **验证**:
  - 合法名称通过
  - 空白、超长、非法字符、重名名称被拒绝
  - 同名创建与重命名都能命中统一校验
- **对应 US**: `US-02`, `US-03`, `US-06`
- **预计**: 45 分钟

### TASK-04: `ProfileManager` — 创建与重命名 Profile
- **状态**: ✅ 已完成
- **依赖**: TASK-03
- **文件**: `src/core/profile_manager.py`, `tests/test_profile_manager.py`
- **操作**:
  1. 实现创建 Profile：写注册表、创建目录结构、初始化独立子目录
  2. 新建时复制当前激活 Profile 的安全配置子集作为初始配置；`api_key` 不继承，`autostart_enabled` 重置为 `False`
  3. 实现重命名显示名逻辑
  4. 创建失败时回滚不完整目录和注册表残留
- **验证**:
  - 创建后目录结构完整
  - 初始配置来自当前激活 Profile
  - 重命名后显示名更新但目录 `id` 不变
  - 异常中断后不会留下可见但不可用的脏 Profile
- **对应 US**: `US-02`, `US-06`, `US-09`
- **预计**: 60 分钟

---

## 检查点 CP-1：Profile 基础元数据与目录能力就绪

| 检查点 | 完成条件 | commit 范围 |
|--------|---------|-------------|
| CP-1 ProfileManager 基础就绪 | TASK-01 ~ TASK-04 完成 | `TASK-01` ~ `TASK-04` |

**检查项**：
- [x] 默认 Profile 元数据可自动初始化
- [x] 名称规则和 `id` 规则明确
- [x] 创建 / 重命名已有可测试实现
- [x] 失败回滚基础能力具备

---

## 第二层：迁移、路径注入与底层兼容改造

### TASK-05: `ProfileManager` — 单目录旧数据 bootstrap 迁移
- **状态**: ✅ 已完成
- **依赖**: TASK-04
- **文件**: `src/core/profile_manager.py`, `tests/test_profile_manager.py`
- **操作**:
  1. 检测老版本单目录模式
  2. 将旧目录数据安全迁移到 `profiles/main/`
  3. 生成迁移记录文件
  4. 仅在迁移成功后写入激活状态
  5. 保留原始数据安全兜底，避免直接覆盖
- **验证**:
  - 旧目录存在时可完成 bootstrap
  - 迁移成功后默认 Profile 数据可读取
  - 迁移异常时原始数据保留且不会写入错误激活状态
- **对应 US**: `US-01`, `US-09`
- **预计**: 60 分钟

### TASK-06: `config.py` / `database.py` — 支持显式 `data_dir` 注入
- **状态**: ✅ 已完成
- **依赖**: TASK-05
- **文件**: `src/core/config.py`, `src/core/database.py`, `tests/test_config.py`, `tests/test_database.py`
- **操作**:
  1. 改造 `Config(data_dir: Path | None = None)`
  2. 改造 `Database(data_dir: Path | None = None)`
  3. 保持默认构造兼容旧逻辑
  4. 确认配置文件、数据库文件、备份目录都来自传入目录
- **验证**:
  - 不传 `data_dir` 时兼容旧行为
  - 传入临时目录时文件全部写入指定位置
  - 既有配置/数据库核心测试无回归
- **对应 US**: `US-07`, `US-08`
- **预计**: 45 分钟

### TASK-07: `logger.py` 与底层路径使用点统一收口
- **状态**: ✅ 已完成
- **依赖**: TASK-06
- **文件**: `src/services/logger.py`, `src/services/timer_engine.py`, `src/services/holiday_manager.py`, `tests/...`
- **操作**:
  1. 确认日志目录由外部显式传入当前 Profile `log_dir`
  2. 检查 `HolidayManager`、定时器相关数据目录是否都从 `Config.get_data_dir()` 或 Profile 路径派生
  3. 搜索并清理新增链路中的硬编码 `.pomato` 路径
- **验证**:
  - 指定 Profile 或 `data_dir` 时日志写入正确目录
  - 节假日缓存落在当前 Profile 目录
  - 搜索结果中不再新增不受控路径写入点
- **对应 US**: `US-07`, `US-08`
- **预计**: 45 分钟

---

## 检查点 CP-2：底层数据隔离能力就绪

| 检查点 | 完成条件 | commit 范围 |
|--------|---------|-------------|
| CP-2 路径注入与迁移就绪 | TASK-05 ~ TASK-07 完成 | `TASK-05` ~ `TASK-07` |

**检查项**：
- [x] 老用户升级路径可工作
- [x] `Config` / `Database` / 日志 / 缓存能落到指定目录
- [x] 测试可以显式使用临时目录运行
- [x] 不再依赖隐式单目录写入完成核心逻辑

---

## 第三层：L4 启动编排与自动重启切换

### TASK-08: `main.py` — 启动参数解析与 Profile 选择优先级
- **状态**: ✅ 已完成
- **依赖**: TASK-07
- **文件**: `main.py`, `tests/test_e2e.py` 或新增启动参数测试文件
- **操作**:
  1. 增加 `--profile <id>` 与 `--data-dir <path>` 参数解析
  2. 定义优先级：`--data-dir` > `--profile` > `profile_state.json`
  3. 在启动早期构造 `ProfileManager` 并决定当前数据目录
  4. Profile 不存在时明确失败并终止启动
- **验证**:
  - `--profile` 能加载指定已存在 Profile
  - `--data-dir` 能直接使用指定目录
  - 不存在的 Profile 启动时报错
- **对应 US**: `US-07`
- **预计**: 45 分钟

### TASK-09: `main.py` / `app.py` — 基于当前 Profile 启动全链路对象
- **状态**: ✅ 已完成
- **依赖**: TASK-08
- **文件**: `main.py`, `src/app.py`, 相关测试文件
- **操作**:
  1. 用当前 Profile 的 `log_dir` 初始化日志
  2. 用当前 Profile `data_dir` 构造 `Config` 与 `Database`
  3. 确保 `ReminderEngine`、`TimerEngine`、`TrayManager` 读取的是同一 Profile 上下文
  4. 如需要，在主窗口或托盘 tooltip 中预留当前 Profile 显示点
- **验证**:
  - 指定不同 Profile 启动时读到不同数据
  - 已有主流程启动无回归
  - 所有核心对象共用同一资料目录上下文
- **对应 US**: `US-04`, `US-08`
- **预计**: 45 分钟

### TASK-10: 自动重启切换执行链路
- **状态**: ✅ 已完成
- **依赖**: TASK-09
- **文件**: `src/app.py`, 可能新增 `src/services/restart_helper.py`, 测试文件
- **操作**:
  1. 实现切换 Profile 后保存 `active_profile_id`
  2. 生成安全的重启命令，重启当前应用进程
  3. 失败时保留用户可手动重启的恢复路径
  4. 避免在同一进程中做热切换
- **验证**:
  - 切换后能写入新激活状态
  - 重启命令构造正确
  - 重启失败时不会破坏原有资料
- **对应 US**: `US-04`, `US-09`
- **预计**: 60 分钟

---

## 检查点 CP-3：非 UI 的完整切换链路就绪

| 检查点 | 完成条件 | commit 范围 |
|--------|---------|-------------|
| CP-3 启动与切换编排就绪 | TASK-08 ~ TASK-10 完成 | `TASK-08` ~ `TASK-10` |

**检查项**：
- [x] 应用可按指定 Profile / 指定目录启动
- [x] 应用对象链路共享同一 Profile 上下文
- [x] 切换后自动重启逻辑闭环成立
- [x] 无热切换残留设计

---

## 第四层：L3 UI 接入与回归收口

### TASK-11: 设置页资料空间管理 UI
- **状态**: ✅ 已完成
- **依赖**: TASK-10
- **文件**: `src/ui/settings_window.py`, 可能新增 `src/ui/profile_manager_dialog.py`, `tests/test_*.py`
- **操作**:
  1. 在设置页新增资料空间区域或管理对话框入口
  2. 展示当前资料空间名称与路径
  3. 提供创建、重命名、切换并重启操作
  4. 直接复用 `ProfileManager` 的名称校验与错误信息
- **验证**:
  - 可从设置页完成创建 / 重命名 / 切换操作
  - 非法名称会展示明确错误
  - 当前 Profile 信息可见
- **对应 US**: `US-02`, `US-03`, `US-04`, `US-05`, `US-06`
- **预计**: 60 ~ 90 分钟

### TASK-12: 托盘入口、集成测试与文档更新
- **状态**: ✅ 已完成
- **依赖**: TASK-11
- **文件**: `src/app.py`, `README.md`, `tests/test_main_window.py`, `tests/test_config.py`, `tests/test_database.py`, `tests/test_profile_manager.py`, 其他相关测试
- **操作**:
  1. 托盘菜单新增“切换资料空间...”入口
  2. 补齐 `ProfileManager`、`Config`、`Database`、启动参数、UI 管理入口的测试
  3. 增加隔离性测试，确认不同 Profile 数据互不可见
  4. 更新 README 与必要的路线图/模块说明
- **验证**:
  - 资料空间菜单入口可用
  - 相关测试通过
  - README 与实现范围一致
- **对应 US**: `US-05`, `US-07`, `US-08`, `US-09`
- **预计**: 60 分钟

---

## 检查点 CP-4：首版多 Profile 可交付

| 检查点 | 完成条件 | commit 范围 |
|--------|---------|-------------|
| CP-4 多 Profile 首版可交付 | TASK-11 ~ TASK-12 完成 | `TASK-11` ~ `TASK-12` |

**检查项**：
- [x] 老用户升级可进入默认 Profile
- [x] 可创建 / 重命名 / 切换资料空间
- [x] 切换后自动重启
- [x] 开发 / 测试可显式指定隔离目录
- [x] 不同 Profile 数据彻底隔离
- [x] UI 与文档一致，测试链路完整

---

## 依赖关系图

```text
TASK-01 ProfileManager 路径骨架
  -> TASK-02 注册表与激活状态
  -> TASK-03 名称校验与 id 规则
  -> TASK-04 创建与重命名
       -> TASK-05 旧数据 bootstrap 迁移
       -> TASK-06 Config/Database 支持 data_dir
            -> TASK-07 logger/缓存路径统一
                 -> TASK-08 启动参数与优先级
                      -> TASK-09 当前 Profile 启动全链路
                           -> TASK-10 自动重启切换
                                -> TASK-11 设置页资料空间 UI
                                     -> TASK-12 托盘入口 + 回归测试 + 文档
```

---

## 后续 Backlog（不进入首版开发）

### TASK-13: Profile 删除与安全确认流
- **状态**: ⬜ 未开始
- **依赖**: CP-4
- **说明**: 删除资料空间及其目录，需额外设计安全确认、不可删除当前激活 Profile、误删恢复策略

### TASK-14: Profile 导出 / 导入
- **状态**: ⬜ 未开始
- **依赖**: CP-4
- **说明**: 支持资料空间打包迁移、备份和恢复

### TASK-15: Profile 云同步与跨设备共享
- **状态**: ⬜ 未开始
- **依赖**: CP-4
- **说明**: 属于未来更大范围的数据同步能力，不纳入当前首版
