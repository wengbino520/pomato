"""Tests for src/ui/history_window.py"""

import pytest
from datetime import date

from src.ui.history_window import HistoryWindow


class TestHistoryWindowInit:
    """Window initialization and date loading."""

    def test_window_created_with_title(self, tmp_db, qapp):
        win = HistoryWindow(tmp_db)
        assert win.windowTitle() == "POMATO · 历史日报"
        win.close()

    def test_period_filter_combo_exists(self, tmp_db, qapp):
        win = HistoryWindow(tmp_db)
        assert win.period_filter is not None
        assert win.period_filter.count() == 4
        assert win.period_filter.itemText(0) == "全部"
        assert win.period_filter.itemText(1) == "日报"
        assert win.period_filter.itemText(2) == "周报"
        assert win.period_filter.itemText(3) == "月报"
        win.close()

    def test_empty_db_shows_no_records(self, tmp_db, qapp):
        win = HistoryWindow(tmp_db)
        assert win.date_list.count() >= 1
        assert "暂无记录" in win.date_list.item(0).text()
        win.close()

    def test_initial_date_preselected(self, tmp_db, qapp):
        from tests.test_database import add
        add(tmp_db, date="2026-06-15", session_no=1, content="Test")
        win = HistoryWindow(tmp_db, initial_date="2026-06-15")
        # Should have an entry-only date in the list
        has_date = any(
            win.date_list.item(i) and "2026-06-15" in win.date_list.item(i).text()
            for i in range(win.date_list.count())
        )
        assert has_date
        win.close()


class TestHistoryWindowPeriod:
    """Period-aware loading from reports with different periods."""

    def test_daily_report_shows_with_correct_label(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-15", [], period="daily",
                           ai_summary="摘要", final_report="# 日报测试")
        win = HistoryWindow(tmp_db)
        # Should show with daily emoji + period label
        texts = [win.date_list.item(i).text()
                 for i in range(win.date_list.count())]
        assert any("日报" in t and "2026-06-15" in t for t in texts)
        win.close()

    def test_weekly_report_shows_with_correct_label(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-09", [], period="weekly",
                           ai_summary="周报摘要", final_report="# 周报测试")
        win = HistoryWindow(tmp_db)
        texts = [win.date_list.item(i).text()
                 for i in range(win.date_list.count())]
        assert any("周报" in t and "2026-06-09" in t for t in texts)
        win.close()

    def test_monthly_report_shows_with_correct_label(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-01", [], period="monthly",
                           ai_summary="月报摘要", final_report="# 月报测试")
        win = HistoryWindow(tmp_db)
        texts = [win.date_list.item(i).text()
                 for i in range(win.date_list.count())]
        assert any("月报" in t and "2026-06-01" in t for t in texts)
        win.close()

    def test_same_date_multiple_periods_show_separate_items(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-15", [], period="daily", ai_summary="d")
        tmp_db.save_report("2026-06-15", [], period="weekly", ai_summary="w")
        tmp_db.save_report("2026-06-15", [], period="monthly", ai_summary="m")
        win = HistoryWindow(tmp_db)
        texts = [win.date_list.item(i).text()
                 for i in range(win.date_list.count())]
        assert sum(1 for t in texts if "2026-06-15" in t) == 3
        assert sum(1 for t in texts if "日报" in t and "2026-06-15" in t) == 1
        assert sum(1 for t in texts if "周报" in t and "2026-06-15" in t) == 1
        assert sum(1 for t in texts if "月报" in t and "2026-06-15" in t) == 1
        win.close()

    def test_weekly_only_filter_hides_daily(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-15", [], period="daily", ai_summary="日报")
        tmp_db.save_report("2026-06-09", [], period="weekly", ai_summary="周报")
        win = HistoryWindow(tmp_db)
        # Select "周报" filter (index 2)
        win.period_filter.setCurrentIndex(2)
        texts = [win.date_list.item(i).text()
                 for i in range(win.date_list.count())]
        assert not any("2026-06-15" in t for t in texts), "日报 should be hidden"
        assert any("2026-06-09" in t and "周报" in t for t in texts)
        win.close()

    def test_filter_back_to_all_shows_all_reports(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-15", [], period="daily", ai_summary="d")
        tmp_db.save_report("2026-06-09", [], period="weekly", ai_summary="w")
        win = HistoryWindow(tmp_db)
        # Filter to 周报, then back to 全部
        win.period_filter.setCurrentIndex(2)  # 周报
        win.period_filter.setCurrentIndex(0)  # 全部
        texts = [win.date_list.item(i).text()
                 for i in range(win.date_list.count())]
        assert any("2026-06-15" in t for t in texts)
        assert any("2026-06-09" in t for t in texts)
        win.close()

    def test_period_badge_visible_in_item_text(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-15", [], period="daily",
                           final_report="# Test")
        win = HistoryWindow(tmp_db)
        texts = [win.date_list.item(i).text()
                 for i in range(win.date_list.count())]
        assert any("📅" in t for t in texts), "Daily emoji should be visible"
        win.close()


class TestHistoryWindowItemData:
    """Item data (UserRole) stores (date, period) tuples."""

    def test_report_item_has_period_data(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-15", [], period="daily",
                           final_report="# Test")
        win = HistoryWindow(tmp_db)
        for i in range(win.date_list.count()):
            data = win.date_list.item(i).data(0x0100)  # UserRole
            if data and data[0] == "2026-06-15":
                assert data[1] == "daily"
                break
        else:
            pytest.fail("Did not find 2026-06-15 item with period data")
        win.close()

    def test_entry_only_item_has_none_period(self, tmp_db, qapp):
        from tests.test_database import add
        add(tmp_db, date="2026-06-20", session_no=1, content="Test")
        win = HistoryWindow(tmp_db)
        for i in range(win.date_list.count()):
            data = win.date_list.item(i).data(0x0100)  # UserRole
            if data and data[0] == "2026-06-20":
                assert data[1] is None, "Entry-only date should have None period"
                break
        else:
            pytest.fail("Did not find 2026-06-20 item")
        win.close()


class TestHistoryWindowSelection:
    """Date selection loads correct report content."""

    def test_select_report_shows_content(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-15", [], period="daily",
                           final_report="# Hello World")
        win = HistoryWindow(tmp_db)
        # Find and select the item
        for i in range(win.date_list.count()):
            data = win.date_list.item(i).data(0x0100)
            if data and data[0] == "2026-06-15" and data[1] == "daily":
                win.date_list.setCurrentRow(i)
                break
        assert "# Hello World" in win.preview.toPlainText()
        win.close()

    def test_select_entry_only_date_shows_raw_entries(self, tmp_db, qapp):
        from tests.test_database import add
        add(tmp_db, date="2026-06-20", session_no=1, content="写代码")
        win = HistoryWindow(tmp_db)
        for i in range(win.date_list.count()):
            data = win.date_list.item(i).data(0x0100)
            if data and data[0] == "2026-06-20":
                win.date_list.setCurrentRow(i)
                break
        text = win.preview.toPlainText()
        assert "2026-06-20" in text
        assert "写代码" in text
        win.close()
