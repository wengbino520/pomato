# 提醒 Snooze Bug 修复方案

> 日期: 2026-06-30
> 关联 Issue: [#2](https://github.com/wengbino520/pomato/issues/2)
> 状态: 待确认

---

## 一、背景

用户设置了每天 21:00 的重复提醒，但提醒在早上 ~9:25 触发，且触发时间不精确（不是整点）。

日志分析（CST = UTC+8）：

| UTC 时间 | 本地时间 | 事件 |
|-----------|---------|------|
| 06-28 16:00 | 06-29 00:00 | Reminders reloaded: 4 enabled |
| 06-29 01:00 | 06-29 **09:00** | 工作会话 1 开始 |
| 06-29 01:25 | 06-29 **09:25** | 工作会话 1 结束 |
| 06-29 01:25:53 | 06-29 09:25:53 | **提醒 id=3 被关闭（dismiss）** |

---

## 二、根因分析

### Bug 1（主因）：`snooze_reminder()` 永久覆写了 `remind_time`

`src/services/reminder_engine.py` 第 86-100 行：

```python
def snooze_reminder(self, reminder_id):
    r = self.db.get_reminder(reminder_id)
    snooze_min = r.get("snooze_min", 10)
    now = datetime.now()
    new_minutes = (now.hour * 60 + now.minute + snooze_min) % (24 * 60)
    h, m = divmod(new_minutes, 60)
    new_time_str = f"{h:02d}:{m:02d}"
    self.db.update_reminder(reminder_id,
                            remind_time=new_time_str,    # ← 永久覆写！
                            last_triggered=None)
```

每次点击"延后"按钮，数据库中的 `remind_time` 就被**永久改写**为"当前时间 + snooze 分钟"。对于重复提醒（每天/每周/工作日），这意味着后续所有日期的提醒时间都被改变了。

**场景推演**：用户原本设定每日 21:00 提醒。某天上午 09:15 看到弹出的提醒（可能前一日积累），点击"延后" → `remind_time` 被覆写为 `"09:25"`。此后每天都变成 09:25 提醒，而非原来的 21:00。

### Bug 2（次因）：提醒时间精度被 snooze 破坏

对比逻辑使用精确字符串匹配 `"HH:MM"`：

```python
if r["remind_time"] != current_time_str:
    continue
```

一旦 snooze 将 `remind_time` 改为 `"09:25"`（非整点值），提醒只会在正好 `09:25` 触发，永不再是整点。

### Bug 3（加剧因素）：弹窗队列延迟

会话结束弹窗和提醒弹窗共用 `_active_popup` 队列。如果会话弹窗先弹出，提醒弹窗排队等待。用户感知到的是"提醒延迟到 09:25 才出现"。

---

## 三、技术方案

### 核心思路

Snooze 不应修改 `remind_time`。应引入 `snoozed_until` 字段表示"暂时跳过，直到 X 时间"，到期后自动恢复原始时间。

### 3.1 数据模型变更

`reminders` 表新增列：

```sql
ALTER TABLE reminders ADD COLUMN snoozed_until TEXT;
```

`snoozed_until` 存储 ISO 格式时间戳（如 `"2026-06-29T09:25:00"`）。为 NULL 表示不在 snooze 状态。

### 3.2 `snooze_reminder()` 新逻辑

```python
def snooze_reminder(self, reminder_id):
    r = self.db.get_reminder(reminder_id)
    if not r:
        return
    snooze_min = r.get("snooze_min", 10)
    now = datetime.now()
    snoozed_until = (now + timedelta(minutes=snooze_min)).isoformat()
    # 只写 snoozed_until，不改 remind_time
    self.db.update_reminder(reminder_id,
                            snoozed_until=snoozed_until,
                            last_triggered=None)
    self._reload_reminders()
```

### 3.3 `on_tick()` 新判断逻辑

在扫描提醒前增加 snooze 窗口检查：

```python
for r in self._reminders:
    if r["id"] in self._triggered_today:
        continue
    # 新增：在 snooze 窗口内跳过
    snoozed_until = r.get("snoozed_until")
    if snoozed_until and now.isoformat() < snoozed_until:
        continue
    # 清除过期的 snoozed_until（已到达解除时间）
    if snoozed_until:
        self.db.update_reminder(r["id"], snoozed_until=None)
        r["snoozed_until"] = None

    if r["remind_time"] != current_time_str:
        continue
    # ... 原有触发逻辑
```

### 3.4 `_reload_reminders()` 清理

日期变更时，清理前一天残留的 `snoozed_until` 状态：

```python
def _reload_reminders(self):
    today = date.today().isoformat()
    self._reminders = self.db.get_enabled_reminders()
    # 清理过期的 snoozed_until（跨天自动失效）
    for r in self._reminders:
        if r.get("snoozed_until"):
            su_date = r["snoozed_until"][:10]
            if su_date < today:
                self.db.update_reminder(r["id"], snoozed_until=None)
                r["snoozed_until"] = None
    self._triggered_today = {
        r["id"] for r in self._reminders
        if r.get("last_triggered") == today
    }
```

### 3.5 影响范围

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/core/database.py` | 改 | `_init_db()` migration 新增 `snoozed_until` 列；`update_reminder()` 允许更新 `snoozed_until` |
| `src/services/reminder_engine.py` | 改 | `snooze_reminder()` 不改 `remind_time`；`on_tick()` 增加 snooze 窗口判断；`_reload_reminders()` 清理过期 snooze |
| `tests/test_reminder_engine.py` | 改 | 更新 snooze 测试（不再断言 `remind_time` 改变）；新增 snooze 窗口测试 |
| `tests/test_e2e.py` | 改 | 更新 e2e snooze 测试 |
| `tests/test_database_reminders.py` | 改 | 新增 `snoozed_until` 读写测试 |

### 3.6 不改的范围

- **ReminderPopup UI**：无变化，按钮和信号不变
- **`app.py` 弹窗队列**：无变化
- **`snooze_reminder` 对外签名**：无变化

---

## 四、风险与权衡

| 风险 | 概率 | 缓解 |
|------|------|------|
| 已有用户的错误 `remind_time` 无法自动修复 | 高 | 无法自动恢复（原始时间已丢失），用户需手动重新设置；可在发版说明中提示 |
| `snoozed_until` migration 在旧 DB 上执行失败 | 低 | 使用 `try: ALTER TABLE ... except: pass` 模式，与现有 migration 一致 |
| 内存中 `snoozed_until` 与 DB 不同步 | 低 | `on_tick()` 中实时清除过期值并同步回 DB |

---

## 五、用户故事

### US-01: 延后按钮不改变原始提醒时间
> 优先级: P0

**作为** 拥有重复提醒（每天/每周/工作日）的用户，
**我希望** 点击"延后"后，提醒仅在当次跳过、稍后再次提醒，
**以便** 明天的同一时间仍然按我最初设定的时刻触发。

**验收标准**：
- [ ] Given 每日 21:00 提醒触发，When 用户在 09:15 点击"延后"，Then 数据库中 `remind_time` 保持 `"21:00"` 不变
- [ ] Given 每日提醒已延后，When 到达次日 21:00，Then 提醒正常触发

### US-02: Snooze 窗口内暂停触发
> 优先级: P0

**作为** 用户，
**我希望** 延后期间提醒不再反复弹出，
**以便** 我正在忙时不受打扰。

**验收标准**：
- [ ] Given 提醒延后 10 分钟，When 在延后窗口内到达匹配时间，Then 提醒不触发
- [ ] Given 提醒延后已过期，When 到达下一个匹配时间，Then 提醒正常触发

### US-03: 跨天自动清理 Snooze 状态
> 优先级: P1

**作为** 用户，
**我希望** 过了一天后延后状态自动清除，
**以便** 昨天的延后不会影响今天的提醒。

**验收标准**：
- [ ] Given 昨日延后了提醒，When 今天 `_reload_reminders()` 执行，Then `snoozed_until` 被清除

---

## 六、测试策略

| 维度 | 测试点 |
|------|--------|
| Snooze 不修改 `remind_time` | snooze 后 `remind_time` 保持原值 |
| Snooze 设置 `snoozed_until` | snooze 后 `snoozed_until` 为 `now + snooze_min` |
| Snooze 窗口内不触发 | `snoozed_until` > now 时即使时间匹配也不触发 |
| Snooze 窗口过期后恢复触发 | `snoozed_until` <= now 时正常触发 |
| 跨天清理 snooze | 次日 `_reload_reminders()` 清除过期的 `snoozed_until` |
| 重复提醒时间不被破坏 | 每天提醒 snooze 后第二天仍按原始时间触发 |
| DB 层 `snoozed_until` 读写 | 写入/读取/更新 `snoozed_until` |
| 向后兼容 | 不传 `snoozed_until` 时行为与修复前一致 |
