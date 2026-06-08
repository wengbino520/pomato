"""
TASK-23: 数据库提醒方法测试
tests/test_database_reminders.py
"""
import pytest


class TestAddReminder:
    """add_reminder 基本正确性。"""

    def test_add_reminder_returns_positive_id(self, tmp_db):
        rid = tmp_db.add_reminder("喝水提醒", "10:00")
        assert isinstance(rid, int)
        assert rid > 0

    def test_add_reminder_defaults(self, tmp_db):
        rid = tmp_db.add_reminder("测试", "14:30")
        r = tmp_db.get_reminder(rid)
        assert r["title"] == "测试"
        assert r["remind_time"] == "14:30"
        assert r["repeat_type"] == "none"
        assert r["enabled"] == 1
        assert r["snooze_min"] == 10

    def test_add_reminder_with_repeat(self, tmp_db):
        rid = tmp_db.add_reminder("每日站会", "09:00",
                                  repeat_type="daily")
        r = tmp_db.get_reminder(rid)
        assert r["repeat_type"] == "daily"

    def test_add_reminder_with_weekday_repeat(self, tmp_db):
        rid = tmp_db.add_reminder("工作日", "08:30",
                                  repeat_type="weekday")
        r = tmp_db.get_reminder(rid)
        assert r["repeat_type"] == "weekday"

    def test_add_reminder_with_weekly_repeat(self, tmp_db):
        rid = tmp_db.add_reminder("周会", "10:00",
                                  repeat_type="weekly",
                                  repeat_days="0,2,4")
        r = tmp_db.get_reminder(rid)
        assert r["repeat_type"] == "weekly"
        assert r["repeat_days"] == "0,2,4"

    def test_add_reminder_custom_snooze(self, tmp_db):
        rid = tmp_db.add_reminder("自定义延后", "15:00", snooze_min=30)
        r = tmp_db.get_reminder(rid)
        assert r["snooze_min"] == 30


class TestGetEnabledReminders:
    """get_enabled_reminders 查询。"""

    def test_returns_only_enabled(self, tmp_db):
        rid1 = tmp_db.add_reminder("启用", "10:00")
        rid2 = tmp_db.add_reminder("禁用", "11:00")
        tmp_db.update_reminder(rid2, enabled=0)
        enabled = tmp_db.get_enabled_reminders()
        ids = [r["id"] for r in enabled]
        assert rid1 in ids
        assert rid2 not in ids

    def test_sorted_by_remind_time(self, tmp_db):
        tmp_db.add_reminder("C", "15:00")
        tmp_db.add_reminder("A", "09:00")
        tmp_db.add_reminder("B", "12:00")
        times = [r["remind_time"] for r in tmp_db.get_enabled_reminders()]
        assert times == ["09:00", "12:00", "15:00"]

    def test_empty_when_no_enabled(self, tmp_db):
        rid = tmp_db.add_reminder("T", "10:00")
        tmp_db.update_reminder(rid, enabled=0)
        assert tmp_db.get_enabled_reminders() == []


class TestGetAllReminders:
    """get_all_reminders 查询。"""

    def test_returns_all_including_disabled(self, tmp_db):
        rid1 = tmp_db.add_reminder("启用", "10:00")
        rid2 = tmp_db.add_reminder("禁用", "11:00")
        tmp_db.update_reminder(rid2, enabled=0)
        all_r = tmp_db.get_all_reminders()
        ids = [r["id"] for r in all_r]
        assert rid1 in ids
        assert rid2 in ids

    def test_sorted_by_remind_time(self, tmp_db):
        tmp_db.add_reminder("B", "14:00")
        tmp_db.add_reminder("A", "08:00")
        times = [r["remind_time"] for r in tmp_db.get_all_reminders()]
        assert times == ["08:00", "14:00"]


class TestGetReminder:
    """get_reminder 单条查询。"""

    def test_returns_dict(self, tmp_db):
        rid = tmp_db.add_reminder("X", "12:00")
        r = tmp_db.get_reminder(rid)
        assert isinstance(r, dict)
        assert r["title"] == "X"

    def test_returns_none_for_missing(self, tmp_db):
        assert tmp_db.get_reminder(99999) is None


class TestUpdateReminder:
    """update_reminder 修改。"""

    def test_update_title(self, tmp_db):
        rid = tmp_db.add_reminder("旧", "10:00")
        tmp_db.update_reminder(rid, title="新")
        assert tmp_db.get_reminder(rid)["title"] == "新"

    def test_update_time(self, tmp_db):
        rid = tmp_db.add_reminder("T", "10:00")
        tmp_db.update_reminder(rid, remind_time="11:00")
        assert tmp_db.get_reminder(rid)["remind_time"] == "11:00"

    def test_update_enabled(self, tmp_db):
        rid = tmp_db.add_reminder("T", "10:00")
        tmp_db.update_reminder(rid, enabled=0)
        assert tmp_db.get_reminder(rid)["enabled"] == 0

    def test_update_repeat_type(self, tmp_db):
        rid = tmp_db.add_reminder("T", "10:00")
        tmp_db.update_reminder(rid, repeat_type="daily")
        assert tmp_db.get_reminder(rid)["repeat_type"] == "daily"

    def test_update_snooze_min(self, tmp_db):
        rid = tmp_db.add_reminder("T", "10:00")
        tmp_db.update_reminder(rid, snooze_min=60)
        assert tmp_db.get_reminder(rid)["snooze_min"] == 60

    def test_update_ignores_unknown_fields(self, tmp_db):
        rid = tmp_db.add_reminder("T", "10:00")
        tmp_db.update_reminder(rid, bad_field=123)  # should not crash


class TestDeleteReminder:
    """delete_reminder 删除。"""

    def test_delete_removes_record(self, tmp_db):
        rid = tmp_db.add_reminder("X", "10:00")
        tmp_db.delete_reminder(rid)
        assert tmp_db.get_reminder(rid) is None

    def test_delete_nonexistent_no_error(self, tmp_db):
        tmp_db.delete_reminder(99999)


class TestMarkReminderTriggered:
    """mark_reminder_triggered 记录触发时间。"""

    def test_marks_last_triggered(self, tmp_db):
        rid = tmp_db.add_reminder("T", "10:00")
        tmp_db.mark_reminder_triggered(rid, "2026-06-09")
        r = tmp_db.get_reminder(rid)
        assert r["last_triggered"] == "2026-06-09"

    def test_overwrites_previous_trigger_date(self, tmp_db):
        rid = tmp_db.add_reminder("T", "10:00")
        tmp_db.mark_reminder_triggered(rid, "2026-06-08")
        tmp_db.mark_reminder_triggered(rid, "2026-06-09")
        assert tmp_db.get_reminder(rid)["last_triggered"] == "2026-06-09"
