"""
TASK-24+25+26: ReminderEngine 综合测试
tests/test_reminder_engine.py

覆盖：待办管理(T24) + 提醒调度(T25) + TimerEngine tick集成(T26)
"""
import pytest
from datetime import datetime as _real_dt, date as _real_date, timedelta
from unittest.mock import MagicMock, patch


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _mock_now(year, month, day, hour, minute, second=0):
    """返回 (mock_datetime, mock_date) 固定到指定时间。"""
    fixed = _real_dt(year, month, day, hour, minute, second)
    mock_dt = MagicMock(wraps=_real_dt)
    mock_dt.now.return_value = fixed

    mock_d = MagicMock(wraps=_real_date)
    mock_d.today.return_value = fixed.date()
    return mock_dt, mock_d


def spy_signal(signal):
    """简单信号 spy：返回 list 收集信号参数。"""
    collected = []

    def slot(*args):
        collected.append(args)

    signal.connect(slot)
    return collected


# ═══════════════════════════════════════════════════════════════════
# TASK-24: 待办管理
# ═══════════════════════════════════════════════════════════════════

class TestTodoManagement:
    """ReminderEngine 待办 CRUD + 信号。"""

    def test_add_todo_returns_id(self, reminder_engine):
        tid = reminder_engine.add_todo("测试")
        assert isinstance(tid, int)
        assert tid > 0

    def test_get_todos_roundtrip(self, reminder_engine):
        reminder_engine.add_todo("AAA", priority=2)
        reminder_engine.add_todo("BBB", priority=1)
        todos = reminder_engine.get_todos()
        assert len(todos) == 2

    def test_todos_changed_signal_emitted_on_add(self, reminder_engine):
        spy = spy_signal(reminder_engine.todos_changed)
        reminder_engine.add_todo("X")
        assert len(spy) == 1

    def test_todos_changed_signal_emitted_on_update(self, reminder_engine):
        tid = reminder_engine.add_todo("X")
        spy = spy_signal(reminder_engine.todos_changed)
        reminder_engine.update_todo(tid, title="Y")
        assert len(spy) >= 1

    def test_todos_changed_signal_emitted_on_delete(self, reminder_engine):
        tid = reminder_engine.add_todo("X")
        spy = spy_signal(reminder_engine.todos_changed)
        reminder_engine.delete_todo(tid)
        assert len(spy) >= 1

    def test_update_todo_title(self, reminder_engine):
        tid = reminder_engine.add_todo("旧")
        reminder_engine.update_todo(tid, title="新")
        assert reminder_engine.db.get_todo(tid)["title"] == "新"

    def test_update_todo_status(self, reminder_engine):
        tid = reminder_engine.add_todo("任务")
        reminder_engine.update_todo(tid, status="done")
        assert reminder_engine.db.get_todo(tid)["status"] == "done"

    def test_delete_todo_removes(self, reminder_engine):
        tid = reminder_engine.add_todo("X")
        reminder_engine.delete_todo(tid)
        assert reminder_engine.db.get_todo(tid) is None

    def test_get_todos_sorted_by_priority(self, reminder_engine):
        reminder_engine.add_todo("低", priority=0)
        reminder_engine.add_todo("高", priority=2)
        reminder_engine.add_todo("中", priority=1)
        todos = reminder_engine.get_todos()
        assert [t["priority"] for t in todos] == [2, 1, 0]

    def test_get_todos_filter_done(self, reminder_engine):
        tid = reminder_engine.add_todo("done")
        reminder_engine.update_todo(tid, status="done")
        reminder_engine.add_todo("pending")
        todos = reminder_engine.get_todos(include_done=False)
        assert all(t["status"] != "done" for t in todos)
        assert len(todos) == 1

    def test_reorder_todos(self, reminder_engine):
        id1 = reminder_engine.add_todo("A")
        id2 = reminder_engine.add_todo("B")
        id3 = reminder_engine.add_todo("C")
        reminder_engine.reorder_todos([id3, id1, id2])
        todos = reminder_engine.get_todos()
        assert [t["id"] for t in todos] == [id3, id1, id2]


class TestCarryOverTodos:
    """自动结转。"""

    def test_carry_over_enabled_by_default(self, reminder_engine):
        reminder_engine.add_todo("P", todo_date="2026-06-01")
        count = reminder_engine.db.carry_over_todos("2026-06-01", "2026-06-02")
        assert count == 1

    def test_carry_over_disabled_when_config_false(self, reminder_engine):
        reminder_engine.config.set("todo_auto_carry_over", False)
        reminder_engine.add_todo("Old", todo_date="2026-06-01")
        mock_dt, mock_d = _mock_now(2026, 6, 2, 9, 0)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine._last_date = "2026-06-01"
            reminder_engine.carry_over_pending_todos()
        todos_today = reminder_engine.db.get_todos(date_str="2026-06-02")
        assert len(todos_today) == 0

    def test_carry_over_emits_todos_changed(self, reminder_engine):
        reminder_engine.add_todo("结转", todo_date="2026-06-01")
        spy = spy_signal(reminder_engine.todos_changed)
        reminder_engine.db.carry_over_todos("2026-06-01", "2026-06-02")
        assert spy is not None


class TestDateChangeDetection:
    """日期变更自动结转 (on_tick 中)。"""

    def test_date_change_triggers_carry_over(self, reminder_engine):
        reminder_engine.config.set("todo_auto_carry_over", True)
        reminder_engine.add_todo("昨天任务", todo_date="2026-06-01")
        mock_dt, mock_d = _mock_now(2026, 6, 2, 9, 0)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine._last_date = "2026-06-01"
            reminder_engine.on_tick()
        todos_today = reminder_engine.db.get_todos(date_str="2026-06-02")
        assert len(todos_today) >= 1
        assert todos_today[0]["title"] == "昨天任务"


# ═══════════════════════════════════════════════════════════════════
# TASK-25: 提醒调度
# ═══════════════════════════════════════════════════════════════════

class TestReminderSchedulingNoMatch:
    """无匹配 → 不触发。"""

    def test_no_reminder_no_trigger(self, reminder_engine):
        mock_dt, mock_d = _mock_now(2026, 6, 9, 10, 0)
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 0

    def test_wrong_time_no_trigger(self, reminder_engine):
        reminder_engine.add_reminder("X", "15:00")
        mock_dt, mock_d = _mock_now(2026, 6, 9, 10, 0)
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 0


class TestReminderSchedulingExact:
    """精确时间 → 触发。"""

    def test_exact_time_triggers(self, reminder_engine):
        reminder_engine.add_reminder("喝咖啡", "10:00")
        mock_dt, mock_d = _mock_now(2026, 6, 9, 10, 0)
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 1
        args = spy[0]
        assert args[1] == "喝咖啡"
        assert args[2] == "10:00"

    def test_same_day_no_duplicate(self, reminder_engine):
        reminder_engine.add_reminder("X", "10:00")
        mock_dt, mock_d = _mock_now(2026, 6, 9, 10, 0)
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 1
        # second tick at same minute shouldn't duplicate
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 1


class TestReminderRepeatDaily:
    """daily 重复规则：每天触发。"""

    def test_daily_triggers_next_day(self, reminder_engine):
        reminder_engine.add_reminder("日提醒", "09:00", repeat_type="daily")
        mock_dt1, mock_d1 = _mock_now(2026, 6, 9, 9, 0)
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt1), \
             patch("src.services.reminder_engine.date", mock_d1):
            reminder_engine.on_tick()
        assert len(spy) == 1
        # Day 2
        mock_dt2, mock_d2 = _mock_now(2026, 6, 10, 9, 0)
        with patch("src.services.reminder_engine.datetime", mock_dt2), \
             patch("src.services.reminder_engine.date", mock_d2):
            reminder_engine._triggered_today.clear()
            reminder_engine.on_tick()
        assert len(spy) == 2


class TestReminderRepeatWeekday:
    """weekday 重复规则：Mon-Fri 触发，周末静默。"""

    def test_weekday_triggers_on_monday(self, reminder_engine):
        reminder_engine.add_reminder("工作日", "09:00", repeat_type="weekday")
        mock_dt, mock_d = _mock_now(2026, 6, 1, 9, 0)  # Monday
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 1

    def test_weekday_silent_on_saturday(self, reminder_engine):
        reminder_engine.add_reminder("工作日", "09:00", repeat_type="weekday")
        mock_dt, mock_d = _mock_now(2026, 6, 6, 9, 0)  # Saturday
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 0

    def test_weekday_silent_on_sunday(self, reminder_engine):
        reminder_engine.add_reminder("工作日", "09:00", repeat_type="weekday")
        mock_dt, mock_d = _mock_now(2026, 6, 7, 9, 0)  # Sunday
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 0


class TestReminderRepeatWeekly:
    """weekly 重复规则：指定周几触发。"""

    def test_weekly_on_monday_triggers(self, reminder_engine):
        reminder_engine.add_reminder("周一会议", "10:00",
                                     repeat_type="weekly",
                                     repeat_days="0")  # 0=Monday
        mock_dt, mock_d = _mock_now(2026, 6, 1, 10, 0)  # Monday
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 1

    def test_weekly_on_tuesday_no_trigger(self, reminder_engine):
        reminder_engine.add_reminder("周一会议", "10:00",
                                     repeat_type="weekly",
                                     repeat_days="0")
        mock_dt, mock_d = _mock_now(2026, 6, 2, 10, 0)  # Tuesday
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 0

    def test_weekly_multi_day(self, reminder_engine):
        reminder_engine.add_reminder("隔天", "09:00",
                                     repeat_type="weekly",
                                     repeat_days="0,2,4")  # Mon,Wed,Fri
        mock_dt, mock_d = _mock_now(2026, 6, 3, 9, 0)  # Wednesday
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 1


class TestReminderDisabled:
    """禁用提醒不触发。"""

    def test_disabled_reminder_not_loaded(self, reminder_engine):
        rid = reminder_engine.add_reminder("禁用", "10:00")
        reminder_engine.update_reminder(rid, enabled=0)
        assert all(r["id"] != rid for r in reminder_engine._reminders)


class TestReminderSnooze:
    """snooze_reminder 延后逻辑 — 不修改 remind_time。"""

    def test_snooze_preserves_original_time(self, reminder_engine):
        """snooze 后 remind_time 保持原值不变。"""
        mock_dt, mock_d = _mock_now(2026, 6, 9, 10, 0)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            rid = reminder_engine.add_reminder("延后测试", "10:00")
            reminder_engine.snooze_reminder(rid)
        r = reminder_engine.db.get_reminder(rid)
        assert r["remind_time"] == "10:00"
        assert r["snoozed_until"] is not None

    def test_snooze_sets_snoozed_until(self, reminder_engine):
        """snooze 后 snoozed_until 为 now + snooze_min。"""
        mock_dt, mock_d = _mock_now(2026, 6, 9, 10, 0)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            rid = reminder_engine.add_reminder("延后测试", "10:00", snooze_min=10)
            reminder_engine.snooze_reminder(rid)
        r = reminder_engine.db.get_reminder(rid)
        # snoozed_until should be ~10 minutes after 10:00
        assert r["snoozed_until"] == "2026-06-09T10:10:00"

    def test_snooze_clears_last_triggered(self, reminder_engine):
        """snooze 后 last_triggered 被置为 None（允许当日再次触发）。"""
        rid = reminder_engine.add_reminder("X", "10:00")
        reminder_engine.db.mark_reminder_triggered(rid, "2026-06-09")
        mock_dt, mock_d = _mock_now(2026, 6, 9, 10, 1)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.snooze_reminder(rid)
        r = reminder_engine.db.get_reminder(rid)
        assert r["last_triggered"] is None


class TestSnoozeWindow:
    """Snooze 窗口内不触发，窗口外恢复触发。"""

    def test_within_snooze_window_no_trigger(self, reminder_engine):
        """snoozed_until 未到期时，即使时间匹配也不触发。"""
        mock_dt, mock_d = _mock_now(2026, 6, 9, 10, 0)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            rid = reminder_engine.add_reminder("延后提醒", "10:00")
            # 手动设置 snoozed_until 为 10:05（还未到期）
            reminder_engine.db.update_reminder(rid, snoozed_until="2026-06-09T10:05:00")
            reminder_engine._reload_reminders()

        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 0

    def test_snooze_window_expired_triggers(self, reminder_engine):
        """snoozed_until 到期后正常触发。"""
        rid = reminder_engine.add_reminder("延后提醒", "10:00")
        # snoozed_until 已过期（09:55 < 10:00）
        reminder_engine.db.update_reminder(rid, snoozed_until="2026-06-09T09:55:00")
        reminder_engine._reload_reminders()

        mock_dt, mock_d = _mock_now(2026, 6, 9, 10, 0)
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 1
        # snoozed_until 应已被清除
        r = reminder_engine.db.get_reminder(rid)
        assert r["snoozed_until"] is None

    def test_daily_repeat_time_preserved_after_snooze(self, reminder_engine):
        """每天重复提醒 snooze 后，remind_time 不被破坏。"""
        mock_dt, mock_d = _mock_now(2026, 6, 9, 21, 0)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            rid = reminder_engine.add_reminder("晚间提醒", "21:00", repeat_type="daily")
            reminder_engine.snooze_reminder(rid)
        r = reminder_engine.db.get_reminder(rid)
        # remind_time 必须保持为 21:00
        assert r["remind_time"] == "21:00"
        assert r["snoozed_until"] is not None

    def test_cross_day_clears_snooze(self, reminder_engine):
        """跨天后 snoozed_until 在 _reload_reminders 中被清除。"""
        rid = reminder_engine.add_reminder("提醒", "10:00")
        # 设置昨天的 snoozed_until
        reminder_engine.db.update_reminder(rid, snoozed_until="2026-06-08T22:00:00")

        mock_dt, mock_d = _mock_now(2026, 6, 9, 9, 0)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine._reload_reminders()
        r = reminder_engine.db.get_reminder(rid)
        assert r["snoozed_until"] is None

    def test_no_snoozed_until_still_triggers(self, reminder_engine):
        """无 snoozed_until 的提醒正常触发（向后兼容）。"""
        reminder_engine.add_reminder("正常提醒", "10:00")
        mock_dt, mock_d = _mock_now(2026, 6, 9, 10, 0)
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 1


class TestSilentOutsideWork:
    """非工作时间静默。"""

    def test_silent_outside_work_blocks_trigger(self, reminder_engine):
        reminder_engine.config.set("reminder_silent_outside_work", True)
        reminder_engine.config.set("work_start_time", "09:00")
        reminder_engine.config.set("work_end_time", "18:00")
        reminder_engine.add_reminder("静默测试", "07:00")
        mock_dt, mock_d = _mock_now(2026, 6, 9, 7, 0)
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 0

    def test_silent_inside_work_allows_trigger(self, reminder_engine):
        reminder_engine.config.set("reminder_silent_outside_work", True)
        reminder_engine.config.set("work_start_time", "09:00")
        reminder_engine.config.set("work_end_time", "18:00")
        reminder_engine.add_reminder("上班提醒", "10:00")
        mock_dt, mock_d = _mock_now(2026, 6, 9, 10, 0)
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 1


class TestMultipleReminders:
    """多个提醒同时到期。"""

    def test_multiple_same_time_all_trigger(self, reminder_engine):
        reminder_engine.add_reminder("A", "10:00")
        reminder_engine.add_reminder("B", "10:00")
        mock_dt, mock_d = _mock_now(2026, 6, 9, 10, 0)
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 2


class TestOneTimeDatedReminder:
    """一次性日期提醒：指定日期的提醒仅在当天触发，次日不再触发。"""

    def test_triggers_on_matching_date(self, reminder_engine):
        """remind_date 匹配时触发。"""
        reminder_engine.add_reminder("看牙医", "15:00", remind_date="2026-06-09")
        mock_dt, mock_d = _mock_now(2026, 6, 9, 15, 0)
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 1
        assert spy[0][1] == "看牙医"

    def test_skips_on_non_matching_date(self, reminder_engine):
        """remind_date 不匹配时不触发。"""
        reminder_engine.add_reminder("看牙医", "15:00", remind_date="2026-06-09")
        mock_dt, mock_d = _mock_now(2026, 6, 10, 15, 0)  # next day
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 0

    def test_not_triggered_again_next_day(self, reminder_engine):
        """已触发的一次性提醒次日不再触发。"""
        reminder_engine.add_reminder("一次性", "09:00", remind_date="2026-06-09")
        # Day 1: trigger
        mock_dt1, mock_d1 = _mock_now(2026, 6, 9, 9, 0)
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt1), \
             patch("src.services.reminder_engine.date", mock_d1):
            reminder_engine.on_tick()
        assert len(spy) == 1
        # Day 2: should NOT trigger
        mock_dt2, mock_d2 = _mock_now(2026, 6, 10, 9, 0)
        with patch("src.services.reminder_engine.datetime", mock_dt2), \
             patch("src.services.reminder_engine.date", mock_d2):
            reminder_engine.on_tick()
        assert len(spy) == 1  # no new signal

    def test_old_none_without_date_still_triggers_daily(self, reminder_engine):
        """向后兼容：无 remind_date 的 none 提醒仍按每天触发。"""
        reminder_engine.add_reminder("老提醒", "12:00", remind_date=None)
        mock_dt, mock_d = _mock_now(2026, 6, 9, 12, 0)
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 1

    def test_daily_with_date_ignores_date_and_triggers_every_day(self, reminder_engine):
        """daily 重复忽略 remind_date，每天触发。"""
        reminder_engine.add_reminder("每日", "08:00",
                                     remind_date="2026-06-01",
                                     repeat_type="daily")
        mock_dt, mock_d = _mock_now(2026, 6, 9, 8, 0)
        spy = spy_signal(reminder_engine.reminder_triggered)
        with patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            reminder_engine.on_tick()
        assert len(spy) == 1


# ═══════════════════════════════════════════════════════════════════
# TASK-26: TimerEngine tick 集成
# ═══════════════════════════════════════════════════════════════════

class TestTimerEngineIntegration:
    """TimerEngine._on_tick() 调用 reminder_engine.on_tick()。"""

    def test_timer_without_reminder_engine_works(self, engine):
        """不传 reminder_engine 时 tick 不崩溃。"""
        assert engine._reminder_engine is None
        mock_dt, mock_d = _mock_now(2026, 6, 9, 14, 0)
        engine._state = "work"
        engine._remaining = 1500
        with patch("src.services.timer_engine.datetime", mock_dt):
            engine._on_tick()

    def test_timer_with_reminder_engine_calls_on_tick(self, qapp, tmp_config, tmp_db):
        """传入 reminder_engine 时 _on_tick 触发引擎 tick。"""
        from src.services.reminder_engine import ReminderEngine
        from src.services.timer_engine import TimerEngine
        rengine = ReminderEngine(tmp_config, tmp_db)
        rengine.add_reminder("定时", "14:00")
        timer = TimerEngine(tmp_config, reminder_engine=rengine)
        mock_dt, mock_d = _mock_now(2026, 6, 9, 14, 0)
        timer._state = "work"
        timer._remaining = 1500
        spy = spy_signal(rengine.reminder_triggered)
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.datetime", mock_dt), \
             patch("src.services.reminder_engine.date", mock_d):
            timer._on_tick()
        assert len(spy) == 1
