
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtGui import QImage

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


def test_history_window_shows_attachment_list_for_rich_entries(tmp_db, qapp):
    tmp_db.upsert_diary_entry(
        "2026-07-03",
        content="今天的记录",
        content_html="<p>今天的记录</p><img src='C:/fake/a.png'>",
        attachments_json=[{"id": "a", "path": "C:/fake/a.png", "name": "a.png"}],
    )
    win = DiaryHistoryWindow(tmp_db, DummyConfig(), initial_date="2026-07-03")

    assert win.preview_attachments is not None
    assert win.preview_attachments.maximumHeight() > 0
    assert win.preview_attachments.count() == 1
    assert "a.png" in win.preview_attachments.item(0).text()
    win.close()


def test_history_window_uses_clear_layout_for_empty_and_rich_states(tmp_db, qapp):
    win = DiaryHistoryWindow(tmp_db, DummyConfig())
    assert win.preview_title is not None
    assert win.preview_meta is not None
    assert win.preview_context is not None
    assert win.preview_content is not None
    assert win.preview_content.isReadOnly()

    tmp_db.upsert_diary_entry(
        "2026-07-03",
        content="今天的记录",
        content_html="<p>布局正常</p>",
        attachments_json=[{"id": "b", "path": "C:/fake/b.png", "name": "b.png"}],
    )
    win._refresh_preview("2026-07-03")
    assert "布局正常" in win.preview_content.toPlainText()
    assert win.preview_attachments.count() == 1
    win.close()


def test_history_window_filters_items_by_search_keyword(tmp_db, qapp):
    tmp_db.upsert_diary_entry("2026-07-02", content="接口文档已补齐")
    tmp_db.upsert_diary_entry("2026-07-03", content="修复托盘图标")
    win = DiaryHistoryWindow(tmp_db, DummyConfig())

    win.search_input.setText("接口")
    qapp.processEvents()

    assert win.list_widget.count() == 1
    assert "2026-07-02" in win.list_widget.item(0).text()
    assert "接口文档已补齐" in win.preview_content.toPlainText()
    win.close()


def test_history_window_double_click_attachment_opens_local_file(tmp_db, qapp, tmp_path):
    attachment_path = tmp_path / "evidence.png"
    attachment_path.write_bytes(b"fake-image")
    tmp_db.upsert_diary_entry(
        "2026-07-03",
        content="今天的记录",
        content_html="<p>今天的记录</p><img src='C:/fake/evidence.png'>",
        attachments_json=[{"id": "evidence", "path": str(attachment_path), "name": "evidence.png"}],
    )
    win = DiaryHistoryWindow(tmp_db, DummyConfig(), initial_date="2026-07-03")

    with patch("src.ui.diary_history_window.QDesktopServices.openUrl", return_value=True) as open_url:
        win.preview_attachments.itemDoubleClicked.emit(win.preview_attachments.item(0))

    assert open_url.called
    assert Path(open_url.call_args.args[0].toLocalFile()) == attachment_path
    win.close()


def test_history_window_marks_missing_attachment_files(tmp_db, qapp):
    tmp_db.upsert_diary_entry(
        "2026-07-03",
        content="今天的记录",
        content_html="<p>今天的记录</p><img src='C:/fake/missing.png'>",
        attachments_json=[{"id": "missing", "path": "C:/fake/missing.png", "name": "missing.png"}],
    )
    win = DiaryHistoryWindow(tmp_db, DummyConfig(), initial_date="2026-07-03")

    item = win.preview_attachments.item(0)
    assert "缺失" in item.text()
    assert "C:/fake/missing.png" in item.toolTip().replace("\\", "/")
    win.close()


def test_history_window_shows_thumbnail_icon_for_existing_image_attachment(tmp_db, qapp, tmp_path):
    attachment_path = tmp_path / "thumb.png"
    image = QImage(24, 16, QImage.Format.Format_ARGB32)
    image.fill(0xFF33AA66)
    assert image.save(str(attachment_path))

    tmp_db.upsert_diary_entry(
        "2026-07-03",
        content="今天的记录",
        content_html="<p>今天的记录</p><img src='thumb.png'>",
        attachments_json=[{"id": "thumb", "path": str(attachment_path), "name": "thumb.png"}],
    )
    win = DiaryHistoryWindow(tmp_db, DummyConfig(), initial_date="2026-07-03")

    item = win.preview_attachments.item(0)
    assert not item.icon().isNull()
    assert "thumb.png" in item.text()
    win.close()