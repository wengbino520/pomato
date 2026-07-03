# 方案设计：移除待办自动结转，消除跨天重复 Bug

> **日期**：2026-06-30
> **版本**：v1.0
> **关联 Issue**：待办跨天重复（用户反馈）

---

## 1. 背景

用户在 `AGENTS.md` 会话中反馈：待办事项在跨天后会多出重复的几条。基于代码分析，根因已定位到 `carry_over_todos()` 与 `get_todos()` 累加查询的设计冲突。

### 当前两条机制

| # | 机制 | 位置 | 作用 |
|---|------|------|------|
| ① | `carry_over_todos()` | `database.py:550` | INSERT 把昨天 pending 待办**物理复制**一行到今日 |
| ② | `get_todos()` 累加查询 | `database.py:445` | 今日视图 `WHERE todo_date=? OR (todo_date<? AND status!='done')` **逻辑包含**过去未完成项 |

### 重复产生链路

```
Day1: 写报告 (todo_date=Day1, pending)
      → carry_over 不触发（首日）

Day1→2 午夜: carry_over INSERT copy (todo_date=Day2, pending)   ← copy A
Day2 视图:   get_todos 累加查询
      → Day1 原始 (pending, OR todo_date<today 命中)  ← 机制②
      → Day2 copy A (pending, todo_date=today 命中)  ← 机制①
      = 用户看见 2 条！

Day2→3 午夜: carry_over 看到 Day2 copy A 仍是 pending
      → INSERT copy B (todo_date=Day3, pending)

Day3 视图:
      → Day1 + copy A + copy B = ≥3 条
```

**每天持续累积**，两条机制做同一件事但互不兼容 → 1 + 1 = 重复。

---

## 2. 目标

**消除待办跨天重复**，确保同一待办每天只出现一条。

---

## 3. 技术方案：方案 A（推荐）— 关闭结转，保留累加查询

### 3.1 核心思路

`get_todos()` 的累加查询 `OR (todo_date < today AND status != 'done')` 已经让用户每天都能看见未完成的待办 — **不需要物理复制行**。

移除 `carry_over` 调用 = 一条待办始终只有一行数据 → 零重复。

### 3.2 改动范围

| 文件 | 改动 | 说明 |
|------|------|------|
| `src/services/reminder_engine.py` | 移除 `carry_over_pending_todos()` 方法；`on_tick()` 中移除结转调用 | 核心修复 |
| `src/ui/settings_window.py` | 移除"自动结转"复选框 | 不再需要的配置项 |
| `src/core/config.py` | 移除 `todo_auto_carry_over` 默认值 | 废弃配置 |
| `tests/test_reminder_engine.py` | 移除 4 个 carry_over 测试 | 清理 |
| `tests/test_database_todos.py` | 移除 `TestCarryOverTodos` 类（4 个测试） | 清理 |

### 3.3 保留不改

| 文件 | 内容 | 原因 |
|------|------|------|
| `database.py:carry_over_todos()` | 方法保留不删 | 可能有直接调用方，保留方法签名但标注 deprecated |
| `database.py:get_todos()` 累加查询 | 不变 | 它就是正确的显示方式 |
| `src/ui/todo_list_widget.py` | 不变 | 刷新逻辑正常 |

### 3.4 `on_tick()` 变更

```python
# 修改前 (reminder_engine.py:149-153)
if self._last_date is not None and self._last_date != today_str:
    self.carry_over_pending_todos()   # ← 删除行
    self._reload_reminders()
self._last_date = today_str

# 修改后
if self._last_date is not None and self._last_date != today_str:
    self._reload_reminders()          # 保留：跨天刷新提醒
self._last_date = today_str
```

### 3.5 不影响的功能

- ✅ 今日视图始终看到未完成待办（累加查询）
- ✅ 勾选完成 → 不再出现（status='done' 被累加查询排除）
- ✅ 日期导航切换历史日期 → 正常显示（`get_todos(date_str=...)` 对非今日不走累加查询）
- ✅ 弹窗关联待办下拉 → 不受影响

---

## 4. 备选方案对比

| | 方案 A（推荐） | 方案 B |
|------|------|------|
| **做法** | 关闭结转，保留累加查询 | 保留结转，移除累加查询 |
| **改动量** | 小（删除 ~50 行） | 大（需持久化 last_date、Ensure 结转可靠性） |
| **风险** | 极低 | 中（结转不可靠 = 待办丢失） |
| **数据干净度** | 一条待办一行 | 一条待办多天多行 |
| **推荐理由** | 改动最小、最安全 | 改动大、引入新风险 |

---

## 5. 影响评估

| 维度 | 评估 |
|------|------|
| **兼容性** | 不影响已有数据；已有重复行只在新"今天"看到（累加查询），功能层面无感知 |
| **性能** | 正向：移除 INSERT 操作 |
| **测试** | 删除 ~11 个结转相关测试，0 regression 基准维持 |
| **用户体验** | 重复消失，无其他变化 |
| **风险** | 极低 |

---

## 6. 风险权衡

- **风险 1**：移除结转后，如果用户有旧重复数据 → 不影响，重复行在各自 date 上存在，只有"今天"视图会通过累加查询展示多行。用户在"今天"勾选一条为 done → 它不再出现在累加查询中。可选项：后续可写一个一次性清理 migration 删除旧重复。
  - **缓解**：接受现状，重复数据随时间自然淘汰（done 的不再显示）。

- **风险 2**：`carry_over_todos()` 可能有其他调用方 → 经搜索确认 0 外部调用，仅 `reminder_engine.carry_over_pending_todos()` 调用。
  - **缓解**：保留 database 方法签名，仅移除 engine 层调用。
