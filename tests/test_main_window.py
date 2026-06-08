"""
tests/test_main_window.py
主窗口日期切换与按天展示的回归测试。
"""
from datetime import date, timedelta

from PyQt6.QtCore import QObject, QDate, pyqtSignal

from src.ui.main_window import EntryItem, MainWindow


class _DummyTimer(QObject):
    tick = pyqtSignal(int, str)

    def __init__(self):
        super().__init__()

    def manual_start(self):
        pass


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