# 待办去重（移除结转）开发任务清单

> 创建时间: 2026-06-30
> 总预估: 30 分钟（6 个子任务）
> 每个 TASK 完成后 git commit，标题以 `TASK-NN` 结尾

---

## 第一层：核心修复（可并行）

### TASK-01: config.py — 移除 todo_auto_carry_over 默认值
- **状态**: ✅ 已完成
- **依赖**: 无
- **文件**: `src/core/config.py`
- **操作**: 从 `DEFAULT_CONFIG` 字典中删除 `"todo_auto_carry_over": True`
- **验证**: 无需单独测试（旧配置项可安全保留在用户配置文件中，仅不再被读取）
- **预计**: 2 分钟

### TASK-02: reminder_engine.py — 移除 carry_over_pending_todos 方法及调用
- **状态**: ✅ 已完成
- **依赖**: 无
- **文件**: `src/services/reminder_engine.py`
- **操作**:
  1. 删除 `carry_over_pending_todos()` 方法（~10 行）
  2. `on_tick()` 中删除 `self.carry_over_pending_todos()` 调用行
- **验证**: 代码可正常导入（`python -c "from src.services.reminder_engine import ReminderEngine"`）
- **预计**: 5 分钟

### TASK-03: settings_window.py — 移除"自动结转"复选框
- **状态**: ✅ 已完成
- **依赖**: 无
- **文件**: `src/ui/settings_window.py`
- **操作**:
  1. 删除 `self.todo_carry_over = QCheckBox(...)` 行（line 261）
  2. 删除 `mf.addRow("", self.todo_carry_over)` 行（line 262）
  3. 删除 `self.todo_carry_over.setChecked(...)` 加载行（line 325）
  4. 删除 `self.config.set("todo_auto_carry_over", ...)` 保存行（line 354）
- **验证**: `tests/test_main_window.py` 中设置相关测试通过
- **预计**: 5 分钟

---

## 检查点 CP-1：核心修复就绪
**条件**: TASK-01~03 完成 → 结转逻辑已完全移除

---

## 第二层：测试清理 + 回归

### TASK-04: test_reminder_engine.py — 移除结转相关测试
- **状态**: ✅ 已完成
- **依赖**: TASK-02（`carry_over_pending_todos` 方法已移除）
- **文件**: `tests/test_reminder_engine.py`
- **操作**: 删除 `TestCarryOver` 类（4 个测试方法：`test_carry_over_enabled_by_default`、`test_carry_over_disabled_when_config_false`、`test_carry_over_emits_todos_changed`、`test_date_change_triggers_carry_over`）
- **验证**: `python -c "import tests.test_reminder_engine"` 不报错
- **预计**: 5 分钟

### TASK-05: test_database_todos.py — 移除结转测试类
- **状态**: ✅ 已完成
- **依赖**: TASK-01（`carry_over_todos()` DB 方法保留，但测试移除）
- **文件**: `tests/test_database_todos.py`
- **操作**: 删除 `TestCarryOverTodos` 类（4 个测试方法）
- **验证**: `python -c "import tests.test_database_todos"` 不报错
- **预计**: 3 分钟

### TASK-06: 全量回归测试
- **状态**: ✅ 已完成
- **依赖**: TASK-01~05
- **操作**: 运行 `pytest tests/ -v --tb=short`，确认 0 failure
- **验证**: 全部通过，预计减少 ~8 个结转相关测试（当前 484 → 约 476）
- **预计**: 5 分钟

---

## 检查点恢复指南

| 检查点 | 完成条件 | commit 范围 |
|--------|---------|-------------|
| CP-1 核心修复就绪 | TASK-01~03 完成 | `TASK-01` ~ `TASK-03` |
| CP-2 测试清理就绪 | TASK-04~06 完成 | `TASK-04` ~ `TASK-06` |
