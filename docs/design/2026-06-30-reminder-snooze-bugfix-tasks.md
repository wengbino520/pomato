# 提醒 Snooze Bug 修复 — 开发任务清单

> 创建时间: 2026-06-30
> 总预估: ~1.5 小时（6 个子任务）
> 每个 TASK 完成后 git commit，标题以 `TASK-NN` 结尾

---

## 第一层：L1 基础设施（数据库层）

### TASK-01: database.py — migration 新增 snoozed_until 列
- **状态**: ⬜ 未开始
- **依赖**: 无
- **文件**: `src/core/database.py`
- **操作**:
  1. `_init_db()` 中新增 migration：`ALTER TABLE reminders ADD COLUMN snoozed_until TEXT`
  2. 使用 `try: ... except sqlite3.OperationalError` 模式
- **验证**: 新创建的 DB 包含该列；已有 DB 执行 migration 不报错
- **对应 US**: US-01
- **预计**: 10 分钟

---

## 第二层：L2 业务逻辑（引擎层）

### TASK-02: reminder_engine.py — snooze_reminder() 改造
- **状态**: ⬜ 未开始
- **依赖**: TASK-01
- **文件**: `src/services/reminder_engine.py`
- **操作**:
  1. 不再 `UPDATE remind_time`，改为计算 `snoozed_until = now + snooze_min`
  2. 调用 `self.db.update_reminder(rid, snoozed_until=snoozed_until, last_triggered=None)`
  3. 调用 `self._reload_reminders()` 刷新内存
- **验证**: snooze 后 `remind_time` 保持不变；`snoozed_until` 正确设置
- **对应 US**: US-01
- **预计**: 15 分钟

### TASK-03: reminder_engine.py — on_tick() 增加 snooze 窗口判断
- **状态**: ⬜ 未开始
- **依赖**: TASK-02
- **文件**: `src/services/reminder_engine.py`
- **操作**:
  1. 在 `for r in self._reminders:` 循环开头，`_triggered_today` 判断之后，加入 snooze 窗口检查
  2. 如果 `snoozed_until` 存在且 `now < snoozed_until` → `continue`
  3. 如果 `snoozed_until` 已过期 → 清除 DB 中的 `snoozed_until` + 内存中的值
- **验证**: snooze 窗口内不触发；窗口过期后正常触发
- **对应 US**: US-02
- **预计**: 15 分钟

### TASK-04: reminder_engine.py — _reload_reminders() 清理过期 snooze
- **状态**: ⬜ 未开始
- **依赖**: TASK-02
- **文件**: `src/services/reminder_engine.py`
- **操作**:
  1. 加载提醒后，遍历检查 `snoozed_until`
  2. 如果 `snoozed_until` 日期部分 < 今天 → 清除 DB 和内存中的值
- **验证**: 跨天后 `snoozed_until` 被清除；当天内不过早清除
- **对应 US**: US-03
- **预计**: 10 分钟

---

## 检查点

| 检查点 | 完成条件 | commit 范围 |
|--------|---------|-------------|
| CP-1 DB 层就绪 | TASK-01 完成 | `TASK-01` |
| CP-2 引擎层就绪 | TASK-02~04 完成 | `TASK-02` ~ `TASK-04` |

---

## 第三层：L4 测试（与 TASK-02~04 同层并行）

### TASK-05: 更新现有测试 + 新增 snooze 窗口测试
- **状态**: ⬜ 未开始
- **依赖**: TASK-02
- **文件**: `tests/test_reminder_engine.py`, `tests/test_database_reminders.py`, `tests/test_e2e.py`
- **操作**:
  1. `test_reminder_engine.py` — 修改 `test_snooze_changes_time` 为 `test_snooze_preserves_original_time`（断言 `remind_time` 不变）
  2. `test_reminder_engine.py` — 新增 `TestSnoozeWindow` 类：窗口内不触发 + 窗口外恢复触发 + 重复提醒时间不被破坏
  3. `test_database_reminders.py` — 新增 `test_snoozed_until_read_write` 和 `test_snoozed_until_null_by_default`
  4. `test_e2e.py` — 更新 `test_snooze_updates_last_triggered`（确认 `snoozed_until` 字段存在）
- **验证**: `pytest tests/ -v --tb=short` 全部通过，0 regression
- **预计**: 25 分钟

### TASK-06: 全量回归测试
- **状态**: ⬜ 未开始
- **依赖**: TASK-05
- **文件**: 无（运行命令）
- **操作**:
  1. 运行 `pytest tests/ -v --tb=short`
  2. 确认所有 160+ 用例通过，0 failure
- **验证**: 全绿
- **预计**: 5 分钟

---

## 依赖关系图

```
TASK-01 (DB migration)
  └→ TASK-02 (snooze_reminder 改造)
       ├→ TASK-03 (on_tick snooze 窗口)
       ├→ TASK-04 (_reload_reminders 清理)
       └→ TASK-05 (测试更新)
            └→ TASK-06 (全量回归)
```
