"""
tests/test_database.py
Database 模块的正确性、边界值和异常场景测试。
"""
import pytest


# ── 辅助函数 ───────────────────────────────────────────────────────────────────

def add(db, date="2026-06-02", session_no=1,
        start="09:00:00", end="09:25:00",
        content="任务内容", tags=None, skipped=False):
    """快捷添加一条记录，减少重复代码。"""
    return db.add_entry(date, session_no, start, end, content, tags, skipped)


# ── 正确性测试 ─────────────────────────────────────────────────────────────────

class TestAddAndQuery:
    """add_entry / get_entries_by_date 基本正确性。"""

    def test_add_entry_returns_positive_integer_id(self, tmp_db):
        eid = add(tmp_db)
        assert isinstance(eid, int)
        assert eid > 0

    def test_consecutive_adds_return_increasing_ids(self, tmp_db):
        id1 = add(tmp_db, session_no=1)
        id2 = add(tmp_db, session_no=2)
        assert id2 > id1

    def test_get_entries_by_date_returns_correct_record(self, tmp_db):
        add(tmp_db, content="完成了登录功能")
        entries = tmp_db.get_entries_by_date("2026-06-02")
        assert len(entries) == 1
        assert entries[0]["content"] == "完成了登录功能"

    def test_entries_sorted_by_start_time(self, tmp_db):
        add(tmp_db, session_no=3, start="10:00:00", content="C")
        add(tmp_db, session_no=1, start="09:00:00", content="A")
        add(tmp_db, session_no=2, start="09:30:00", content="B")
        # 应按 start_time 排序，而非 session_no
        contents = [e["content"] for e in tmp_db.get_entries_by_date("2026-06-02")]
        assert contents == ["A", "B", "C"]

    def test_tags_deserialized_as_list(self, tmp_db):
        add(tmp_db, tags=["开发", "测试"])
        entry = tmp_db.get_entries_by_date("2026-06-02")[0]
        assert entry["tags"] == ["开发", "测试"]

    def test_null_tags_argument_stored_as_empty_list(self, tmp_db):
        add(tmp_db, tags=None)
        entry = tmp_db.get_entries_by_date("2026-06-02")[0]
        assert entry["tags"] == []

    def test_empty_tags_list_round_trips(self, tmp_db):
        add(tmp_db, tags=[])
        entry = tmp_db.get_entries_by_date("2026-06-02")[0]
        assert entry["tags"] == []

    def test_skipped_flag_stored_correctly(self, tmp_db):
        add(tmp_db, skipped=True)
        entry = tmp_db.get_entries_by_date("2026-06-02")[0]
        assert entry["skipped"] == 1   # SQLite stores as int

    def test_created_at_is_populated(self, tmp_db):
        add(tmp_db)
        entry = tmp_db.get_entries_by_date("2026-06-02")[0]
        assert entry["created_at"] is not None
        assert len(entry["created_at"]) > 10

    def test_wrong_date_returns_empty_list(self, tmp_db):
        add(tmp_db, date="2026-06-02")
        assert tmp_db.get_entries_by_date("2026-06-01") == []

    def test_different_dates_are_isolated(self, tmp_db):
        add(tmp_db, date="2026-06-01", session_no=1)
        add(tmp_db, date="2026-06-02", session_no=1)
        assert len(tmp_db.get_entries_by_date("2026-06-01")) == 1
        assert len(tmp_db.get_entries_by_date("2026-06-02")) == 1


class TestSessionCount:
    """get_today_session_count：仅统计未跳过的记录。"""

    def test_counts_non_skipped_entries(self, tmp_db):
        add(tmp_db, session_no=1, skipped=False)
        add(tmp_db, session_no=2, skipped=False)
        assert tmp_db.get_today_session_count("2026-06-02") == 2

    def test_skipped_entries_not_counted(self, tmp_db):
        add(tmp_db, session_no=1, skipped=False)
        add(tmp_db, session_no=2, skipped=True)
        assert tmp_db.get_today_session_count("2026-06-02") == 1

    def test_all_skipped_returns_zero(self, tmp_db):
        add(tmp_db, session_no=1, skipped=True)
        add(tmp_db, session_no=2, skipped=True)
        assert tmp_db.get_today_session_count("2026-06-02") == 0

    def test_no_entries_returns_zero(self, tmp_db):
        assert tmp_db.get_today_session_count("2026-06-02") == 0

    def test_only_counts_target_date(self, tmp_db):
        add(tmp_db, date="2026-06-01", session_no=1, skipped=False)
        add(tmp_db, date="2026-06-02", session_no=1, skipped=False)
        assert tmp_db.get_today_session_count("2026-06-02") == 1

    def test_get_next_session_no_empty_date(self, tmp_db):
        assert tmp_db.get_next_session_no("2026-06-02") == 1

    def test_get_next_session_no_after_manual_adds(self, tmp_db):
        add(tmp_db, session_no=1, content="手动1")
        add(tmp_db, session_no=2, content="手动2")
        assert tmp_db.get_next_session_no("2026-06-02") == 3

    def test_get_next_session_no_ignores_other_dates(self, tmp_db):
        add(tmp_db, date="2026-06-01", session_no=5)
        assert tmp_db.get_next_session_no("2026-06-02") == 1

    def test_get_latest_valid_entry_content_by_time(self, tmp_db):
        add(tmp_db, session_no=1, start="09:00:00", content="第一个")
        add(tmp_db, session_no=2, start="10:00:00", content="第二个")
        assert tmp_db.get_latest_valid_entry_content("2026-06-02") == "第二个"

    def test_get_latest_valid_entry_skips_empty_content(self, tmp_db):
        add(tmp_db, session_no=1, start="09:00:00", content="有效")
        add(tmp_db, session_no=2, start="10:00:00", content="")
        assert tmp_db.get_latest_valid_entry_content("2026-06-02") == "有效"


class TestUpdateAndDelete:
    """update_entry / delete_entry 基本操作。"""

    def test_update_content(self, tmp_db):
        eid = add(tmp_db, content="旧内容")
        tmp_db.update_entry(eid, "新内容", [])
        entry = tmp_db.get_entries_by_date("2026-06-02")[0]
        assert entry["content"] == "新内容"

    def test_update_tags(self, tmp_db):
        eid = add(tmp_db, tags=["开发"])
        tmp_db.update_entry(eid, "内容", ["会议", "文档"])
        entry = tmp_db.get_entries_by_date("2026-06-02")[0]
        assert entry["tags"] == ["会议", "文档"]

    def test_update_clears_tags_when_empty_list(self, tmp_db):
        eid = add(tmp_db, tags=["开发"])
        tmp_db.update_entry(eid, "内容", [])
        entry = tmp_db.get_entries_by_date("2026-06-02")[0]
        assert entry["tags"] == []

    def test_delete_entry_removes_record(self, tmp_db):
        eid = add(tmp_db)
        tmp_db.delete_entry(eid)
        assert tmp_db.get_entries_by_date("2026-06-02") == []

    def test_delete_only_removes_target_entry(self, tmp_db):
        eid1 = add(tmp_db, session_no=1)
        eid2 = add(tmp_db, session_no=2)
        tmp_db.delete_entry(eid1)
        remaining = tmp_db.get_entries_by_date("2026-06-02")
        assert len(remaining) == 1
        assert remaining[0]["id"] == eid2


class TestReports:
    """save_report / get_report / get_all_report_dates 正确性。"""

    def test_save_and_get_report(self, tmp_db):
        entries = [{"id": 1, "content": "工作内容"}]
        tmp_db.save_report("2026-06-02", entries, ai_summary="摘要", final_report="# 日报")
        report = tmp_db.get_report("2026-06-02")
        assert report is not None
        assert report["ai_summary"] == "摘要"
        assert report["final_report"] == "# 日报"
        assert report["raw_entries"] == entries

    def test_save_report_upsert_overwrites_same_date(self, tmp_db):
        """相同日期再次 save 时覆盖旧值，不新增行。"""
        tmp_db.save_report("2026-06-02", [], ai_summary="v1")
        tmp_db.save_report("2026-06-02", [], ai_summary="v2")
        report = tmp_db.get_report("2026-06-02")
        assert report["ai_summary"] == "v2"
        assert len(tmp_db.get_all_report_dates()) == 1

    def test_get_report_nonexistent_returns_none(self, tmp_db):
        assert tmp_db.get_report("1999-01-01") is None

    def test_raw_entries_serialized_and_deserialized(self, tmp_db):
        entries = [{"id": 1, "tags": ["开发"], "content": "测试内容🚀"}]
        tmp_db.save_report("2026-06-02", entries)
        report = tmp_db.get_report("2026-06-02")
        assert report["raw_entries"][0]["tags"] == ["开发"]
        assert "🚀" in report["raw_entries"][0]["content"]

    def test_get_all_report_dates_descending_order(self, tmp_db):
        tmp_db.save_report("2026-06-01", [])
        tmp_db.save_report("2026-06-03", [])
        tmp_db.save_report("2026-06-02", [])
        dates = tmp_db.get_all_report_dates()
        assert dates == ["2026-06-03", "2026-06-02", "2026-06-01"]

    def test_get_all_report_dates_empty_when_no_reports(self, tmp_db):
        assert tmp_db.get_all_report_dates() == []


# ── 边界值测试 ─────────────────────────────────────────────────────────────────

class TestDatabaseBoundary:
    """边界值：None 内容、超长文本、Unicode、大量记录。"""

    def test_content_none_stored_and_retrieved(self, tmp_db):
        add(tmp_db, content=None)
        entry = tmp_db.get_entries_by_date("2026-06-02")[0]
        assert entry["content"] is None

    def test_very_long_content(self, tmp_db):
        long_content = "测" * 10_000
        add(tmp_db, content=long_content)
        entry = tmp_db.get_entries_by_date("2026-06-02")[0]
        assert entry["content"] == long_content

    def test_unicode_content_and_emoji_tags(self, tmp_db):
        content = "完成 🚀 & <script>alert(1)</script>"
        tags = ["开发🔥", "✅测试"]
        add(tmp_db, content=content, tags=tags)
        entry = tmp_db.get_entries_by_date("2026-06-02")[0]
        assert entry["content"] == content
        assert entry["tags"] == tags

    def test_many_entries_same_day(self, tmp_db):
        for i in range(1, 9):
            add(tmp_db, session_no=i, content=f"任务{i}")
        assert len(tmp_db.get_entries_by_date("2026-06-02")) == 8


# ── 异常场景测试 ───────────────────────────────────────────────────────────────

class TestDatabaseExceptionScenarios:
    """对不存在的 ID 操作应静默忽略，不抛出异常。"""

    def test_delete_nonexistent_id_no_exception(self, tmp_db):
        tmp_db.delete_entry(99999)   # 不应抛出

    def test_update_nonexistent_id_no_exception(self, tmp_db):
        tmp_db.update_entry(99999, "content", [])  # 不应抛出

    def test_database_initializes_idempotently(self, tmp_path):
        """多次初始化 Database 不会破坏已有数据。"""
        from pathlib import Path
        from unittest.mock import patch

        with patch("pathlib.Path.home", return_value=tmp_path):
            from src.core.database import Database
            db = Database()
            eid = db.add_entry("2026-06-02", 1, "09:00:00", "09:25:00", "数据")
            # 再次实例化（等同调用 _init_db 两次）
            db2 = Database()
        entries = db2.get_entries_by_date("2026-06-02")
        assert len(entries) == 1
        assert entries[0]["content"] == "数据"


# ── Reminder with remind_date ──────────────────────────────────────────────────

class TestReminderWithDate:
    """一次性日期提醒的 DB CRUD。"""

    def test_add_reminder_with_date(self, tmp_db):
        rid = tmp_db.add_reminder("看牙医", "15:00", remind_date="2026-06-15")
        r = tmp_db.get_reminder(rid)
        assert r["remind_date"] == "2026-06-15"
        assert r["repeat_type"] == "none"

    def test_add_reminder_without_date(self, tmp_db):
        rid = tmp_db.add_reminder("每日", "09:00")
        r = tmp_db.get_reminder(rid)
        assert r["remind_date"] is None

    def test_update_reminder_date(self, tmp_db):
        rid = tmp_db.add_reminder("会议", "14:00", remind_date="2026-06-10")
        tmp_db.update_reminder(rid, remind_date="2026-06-20")
        r = tmp_db.get_reminder(rid)
        assert r["remind_date"] == "2026-06-20"

    def test_clear_reminder_date(self, tmp_db):
        rid = tmp_db.add_reminder("会议", "14:00", remind_date="2026-06-10")
        tmp_db.update_reminder(rid, remind_date=None)
        r = tmp_db.get_reminder(rid)
        assert r["remind_date"] is None
