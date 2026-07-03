"""
tests/test_main_window.py
主窗口日期切换与按天展示的回归测试。
"""
from datetime import date, timedelta

from PyQt6.QtCore import QObject, QDate, pyqtSignal

from src.ui.main_window import EntryItem, MainWindow


class _DummyTimer(QObject):
    tick = pyqtSignal(int, str)
    state_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._paused = False

    def manual_start(self):
        pass

    def pause_resume(self):
        self._paused = not self._paused


class _DummyConfig:
    def __init__(self):
        self._data = {
            "pomodoro_duration": 25,
            "custom_tags": [],
        }

    def get(self, key, default=None):
        return self._data.get(key, default)


def _first_entry_widget(window: MainWindow):
    for index in range(window.entries_layout.count()):
        widget = window.entries_layout.itemAt(index).widget()
        if isinstance(widget, EntryItem):
            return widget
    return None


def test_main_window_filters_entries_by_selected_date(qapp, tmp_db):
    today = date.today()
    yesterday = today - timedelta(days=1)

    tmp_db.add_entry(today.isoformat(), 1, "09:00:00", "09:25:00", "今天的记录", [])
    tmp_db.add_entry(yesterday.isoformat(), 1, "09:00:00", "09:25:00", "昨天的记录", [])

    window = MainWindow(_DummyConfig(), tmp_db, _DummyTimer())

    first_entry = _first_entry_widget(window)
    assert first_entry is not None
    assert first_entry.entry["date"] == today.isoformat()
    assert window.date_label.text().startswith(today.isoformat())

    window.view_date_edit.setDate(QDate.fromString(yesterday.isoformat(), "yyyy-MM-dd"))
    qapp.processEvents()

    first_entry = _first_entry_widget(window)
    assert first_entry is not None
    assert first_entry.entry["date"] == yesterday.isoformat()
    assert window.date_label.text().startswith(yesterday.isoformat())


def test_main_window_refreshes_diary_widget_by_selected_date(qapp, tmp_db):
    today = date.today()
    yesterday = today - timedelta(days=1)

    tmp_db.upsert_diary_entry(today.isoformat(), content="今天的日记")
    tmp_db.upsert_diary_entry(yesterday.isoformat(), content="昨天的日记")

    window = MainWindow(_DummyConfig(), tmp_db, _DummyTimer())

    assert window._diary_widget._content_edit.toPlainText() == "今天的日记"

    window.view_date_edit.setDate(QDate.fromString(yesterday.isoformat(), "yyyy-MM-dd"))
    qapp.processEvents()

    assert window._diary_widget._content_edit.toPlainText() == "昨天的日记"


# ── EntryItem expand/collapse toggle tests ────────────────────────────────────

def _make_entry(content="测试内容", skipped=False, tags=None):
    return {
        "id": 1, "session_no": 1,
        "start_time": "09:00:00", "end_time": "09:25:00",
        "content": content, "tags": tags or [], "skipped": skipped,
        "date": "2026-06-16", "todo_title": None,
    }


class TestEntryItemToggle:
    """EntryItem 展开/收起功能测试。"""

    def test_content_label_starts_single_line(self, qapp):
        """新建 EntryItem 时，content_lbl 高度被限制为单行。"""
        item = EntryItem(_make_entry(content="这是一段很长的测试内容"))
        assert item._content_lbl.maximumHeight() < 16777215  # 受限
        assert not item._expanded

    def test_toggle_visible_for_non_empty_content(self, qapp):
        """有内容且非 skipped 时，▼ 按钮可见。"""
        item = EntryItem(_make_entry(content="有内容"))
        assert not item._toggle_btn.isHidden()
        assert item._toggle_btn.text() == "▼"

    def test_toggle_hidden_for_empty_content(self, qapp):
        """内容为空时，▼ 按钮隐藏。"""
        item = EntryItem(_make_entry(content=""))
        assert item._toggle_btn.isHidden()

    def test_toggle_hidden_for_skipped_entry(self, qapp):
        """已跳过的条目，▼ 按钮隐藏。"""
        item = EntryItem(_make_entry(content="内容", skipped=True))
        assert item._toggle_btn.isHidden()

    def test_expand_shows_full_text(self, qapp):
        """点击 ▼ 后展开，高度解除限制，显示全文。"""
        item = EntryItem(_make_entry(content="有内容"))
        item._toggle_btn.click()
        assert item._content_lbl.maximumHeight() == 16777215  # unconstrained
        assert item._content_lbl.text() == "有内容"
        assert item._toggle_btn.text() == "▲"

    def test_collapse_restricts_height_again(self, qapp):
        """展开后再点击 ▲ 收起，恢复高度限制。"""
        item = EntryItem(_make_entry(content="有内容"))
        item._toggle_btn.click()  # expand
        item._toggle_btn.click()  # collapse
        assert item._content_lbl.maximumHeight() < 16777215  # restricted
        assert item._toggle_btn.text() == "▼"

    def test_tooltip_changes_on_toggle(self, qapp):
        """展开/收起时 tooltip 同步切换。"""
        item = EntryItem(_make_entry(content="有内容"))
        assert "展开" in item._toggle_btn.toolTip()
        item._toggle_btn.click()
        assert "收起" in item._toggle_btn.toolTip()