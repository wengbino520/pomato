"""Tests for src/ui/history_window.py"""

import pytest
from PyQt6.QtCore import Qt

from src.ui.history_window import HistoryWindow


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _all_leaf_texts(win):
    """Collect text from all leaf items (report dates) across all sections."""
    texts = []
    for i in range(win.date_tree.topLevelItemCount()):
        section = win.date_tree.topLevelItem(i)
        for j in range(section.childCount()):
            child = section.child(j)
            texts.append(child.text(0))
    return texts


def _all_section_texts(win):
    """Collect text from all top-level section headers."""
    return [win.date_tree.topLevelItem(i).text(0)
            for i in range(win.date_tree.topLevelItemCount())]


def _find_leaf(win, date_str, period=None):
    """Find a leaf QTreeWidgetItem by date (and optionally period)."""
    for i in range(win.date_tree.topLevelItemCount()):
        section = win.date_tree.topLevelItem(i)
        for j in range(section.childCount()):
            child = section.child(j)
            data = child.data(0, Qt.ItemDataRole.UserRole)
            if data and data[0] == date_str:
                if period is None or data[1] == period:
                    return child
    return None


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestHistoryWindowInit:
    """Window initialization and tree structure."""

    def test_window_created_with_title(self, tmp_db, qapp):
        win = HistoryWindow(tmp_db)
        assert win.windowTitle() == "POMATO · 历史报告"
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
        assert win.date_tree.topLevelItemCount() == 1
        assert "暂无记录" in win.date_tree.topLevelItem(0).text(0)
        win.close()

    def test_initial_date_preselected(self, tmp_db, qapp):
        from tests.test_database import add
        add(tmp_db, date="2026-06-15", session_no=1, content="Test")
        win = HistoryWindow(tmp_db, initial_date="2026-06-15")
        leaves = _all_leaf_texts(win)
        assert "2026-06-15" in leaves
        win.close()


class TestHistoryWindowSections:
    """Report tree has categorized sections with counts."""

    def test_daily_report_in_daily_section(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-15", [], period="daily",
                           ai_summary="摘要", final_report="# 日报测试")
        win = HistoryWindow(tmp_db)
        sections = _all_section_texts(win)
        assert any("日报" in s for s in sections)
        assert "2026-06-15" in _all_leaf_texts(win)
        win.close()

    def test_weekly_report_in_weekly_section(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-09", [], period="weekly",
                           ai_summary="周报摘要", final_report="# 周报测试")
        win = HistoryWindow(tmp_db)
        sections = _all_section_texts(win)
        assert any("周报" in s for s in sections)
        assert "2026-06-09" in _all_leaf_texts(win)
        win.close()

    def test_monthly_report_in_monthly_section(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-01", [], period="monthly",
                           ai_summary="月报摘要", final_report="# 月报测试")
        win = HistoryWindow(tmp_db)
        sections = _all_section_texts(win)
        assert any("月报" in s for s in sections)
        assert "2026-06-01" in _all_leaf_texts(win)
        win.close()

    def test_same_date_three_periods_in_own_sections(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-15", [], period="daily", ai_summary="d")
        tmp_db.save_report("2026-06-15", [], period="weekly", ai_summary="w")
        tmp_db.save_report("2026-06-15", [], period="monthly", ai_summary="m")
        win = HistoryWindow(tmp_db)
        sections = _all_section_texts(win)
        assert any("日报" in s for s in sections)
        assert any("周报" in s for s in sections)
        assert any("月报" in s for s in sections)
        for period in ("daily", "weekly", "monthly"):
            assert _find_leaf(win, "2026-06-15", period) is not None
        win.close()

    def test_section_header_shows_count(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-15", [], period="daily", ai_summary="a")
        tmp_db.save_report("2026-06-14", [], period="daily", ai_summary="b")
        win = HistoryWindow(tmp_db)
        for i in range(win.date_tree.topLevelItemCount()):
            section = win.date_tree.topLevelItem(i)
            text = section.text(0)
            data = section.data(0, Qt.ItemDataRole.UserRole)
            if data and data[1] == "daily":
                assert "(2)" in text
                break
        else:
            pytest.fail("Daily section not found")
        win.close()

    def test_section_header_not_selectable(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-15", [], period="daily",
                           final_report="# Test")
        win = HistoryWindow(tmp_db)
        # Sections are ItemIsEnabled only, no ItemIsSelectable
        for i in range(win.date_tree.topLevelItemCount()):
            section = win.date_tree.topLevelItem(i)
            flags = section.flags()
            assert not (flags & Qt.ItemFlag.ItemIsSelectable)
        win.close()


class TestHistoryWindowFilter:
    """Period filter works with tree sections."""

    def test_weekly_filter_hides_daily(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-15", [], period="daily", ai_summary="日报")
        tmp_db.save_report("2026-06-09", [], period="weekly", ai_summary="周报")
        win = HistoryWindow(tmp_db)
        win.period_filter.setCurrentIndex(2)  # 周报
        leaves = _all_leaf_texts(win)
        assert "2026-06-15" not in leaves
        assert "2026-06-09" in leaves
        win.close()

    def test_filter_back_to_all(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-15", [], period="daily", ai_summary="d")
        tmp_db.save_report("2026-06-09", [], period="weekly", ai_summary="w")
        win = HistoryWindow(tmp_db)
        win.period_filter.setCurrentIndex(2)  # 周报
        win.period_filter.setCurrentIndex(0)  # 全部
        leaves = _all_leaf_texts(win)
        assert "2026-06-15" in leaves
        assert "2026-06-09" in leaves
        win.close()


class TestHistoryWindowItemData:
    """Leaf item UserRole stores (date, period) tuples."""

    def test_report_leaf_has_period_data(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-15", [], period="daily",
                           final_report="# Test")
        win = HistoryWindow(tmp_db)
        leaf = _find_leaf(win, "2026-06-15")
        assert leaf is not None
        data = leaf.data(0, Qt.ItemDataRole.UserRole)
        assert data[0] == "2026-06-15"
        assert data[1] == "daily"
        win.close()

    def test_entry_only_leaf_has_none_period(self, tmp_db, qapp):
        from tests.test_database import add
        add(tmp_db, date="2026-06-20", session_no=1, content="Test")
        win = HistoryWindow(tmp_db)
        leaf = _find_leaf(win, "2026-06-20")
        assert leaf is not None
        data = leaf.data(0, Qt.ItemDataRole.UserRole)
        assert data[0] == "2026-06-20"
        assert data[1] is None
        win.close()


class TestHistoryWindowSelection:
    """Date selection loads correct report content."""

    def test_select_report_shows_content(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-15", [], period="daily",
                           final_report="# Hello World")
        win = HistoryWindow(tmp_db)
        leaf = _find_leaf(win, "2026-06-15", "daily")
        assert leaf is not None
        win.date_tree.setCurrentItem(leaf)
        assert "# Hello World" in win.preview.toPlainText()
        win.close()

    def test_select_entry_only_shows_raw_entries(self, tmp_db, qapp):
        from tests.test_database import add
        add(tmp_db, date="2026-06-20", session_no=1, content="写代码")
        win = HistoryWindow(tmp_db)
        leaf = _find_leaf(win, "2026-06-20")
        assert leaf is not None
        win.date_tree.setCurrentItem(leaf)
        text = win.preview.toPlainText()
        assert "2026-06-20" in text
        assert "写代码" in text
        win.close()

    def test_sections_are_collapsible(self, tmp_db, qapp):
        tmp_db.save_report("2026-06-15", [], period="daily",
                           final_report="# Test")
        win = HistoryWindow(tmp_db)
        for i in range(win.date_tree.topLevelItemCount()):
            section = win.date_tree.topLevelItem(i)
            data = section.data(0, Qt.ItemDataRole.UserRole)
            if data and data[0] == "__section__":
                section.setExpanded(False)
                assert not section.isExpanded()
                section.setExpanded(True)
                assert section.isExpanded()
                break
        win.close()
