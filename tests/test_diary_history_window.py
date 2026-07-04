
from src.ui.diary_history_window import DiaryHistoryWindow


class DummyConfig:
    def __init__(self, pomodoro_duration=25):
        self._pomodoro_duration = pomodoro_duration

    def get(self, key, default=None):
        if key == "pomodoro_duration":
            return self._pomodoro_duration
        return default


def test_empty_history_window_shows_placeholder(tmp_db, qapp):
    win = DiaryHistoryWindow(tmp_db, DummyConfig())
    assert win.windowTitle() == "POMATO · 日记历史"
    assert win.list_widget.count() == 1
    assert "暂无日记记录" in win.list_widget.item(0).text()
    win.close()


def test_history_window_lists_dates_and_previews_selected_entry(tmp_db, qapp):
    tmp_db.upsert_diary_entry("2026-07-02", content="前一天", mood_score=2, mood_emoji="😐")
    tmp_db.upsert_diary_entry("2026-07-03", content="今天的内容", mood_score=4, mood_emoji="😊")
    win = DiaryHistoryWindow(tmp_db, DummyConfig(), initial_date="2026-07-03")

    assert win.list_widget.count() == 2
    assert "2026-07-03" in win.list_widget.item(0).text()
    assert "今天的内容" in win.preview_content.toPlainText()
    assert "😊" in win.preview_meta.text()
    win.close()


def test_history_window_open_selected_date_callback(tmp_db, qapp):
    collected = []
    tmp_db.upsert_diary_entry("2026-07-03", content="今天")
    win = DiaryHistoryWindow(
        tmp_db,
        DummyConfig(),
        initial_date="2026-07-03",
        on_open_date=collected.append,
    )

    win.open_btn.click()
    assert collected == ["2026-07-03"]
    win.close()


def test_history_window_switch_selection_updates_preview(tmp_db, qapp):
    tmp_db.upsert_diary_entry("2026-07-02", content="前一天", mood_score=2, mood_emoji="😐")
    tmp_db.upsert_diary_entry("2026-07-03", content="今天", mood_score=4, mood_emoji="😊")
    win = DiaryHistoryWindow(tmp_db, DummyConfig())

    win.list_widget.setCurrentRow(1)
    qapp.processEvents()

    assert "前一天" in win.preview_content.toPlainText()
    assert "😐" in win.preview_meta.text()
    win.close()