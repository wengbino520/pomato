from pathlib import Path

from PyQt6.QtCore import QMimeData, QUrl
from PyQt6.QtGui import QImage, QTextCursor

from src.ui.diary_widget import DiaryWidget


class DummyConfig:
    def __init__(self, pomodoro_duration=25):
        self._pomodoro_duration = pomodoro_duration

    def get(self, key, default=None):
        if key == "pomodoro_duration":
            return self._pomodoro_duration
        return default


def test_widget_shows_empty_state_for_new_date(qapp, tmp_db):
    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")

    assert "2026-07-03" in widget._date_label.text()
    assert "今天还没有番茄记录或待办数据" in widget._summary_label.text()
    assert widget._content_edit.toPlainText() == ""
    assert widget._status_label.text() == "尚未保存本日记。"


def test_widget_loads_existing_diary_content_and_state(qapp, tmp_db):
    tmp_db.upsert_diary_entry(
        "2026-07-03",
        content="已有日记",
        mood_score=4,
        mood_emoji="😊",
        energy_score=3,
        stress_score=2,
    )

    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")

    assert widget._content_edit.toPlainText() == "已有日记"
    assert widget._mood_combo.currentData() == (4, "😊")
    assert widget._energy_combo.currentData() == 3
    assert widget._stress_combo.currentData() == 2


def test_widget_save_persists_content_and_state(qapp, tmp_db):
    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")

    widget._content_edit.setPlainText("今天完成了服务层实现")
    widget._mood_combo.setCurrentIndex(4)  # 😊 4
    widget._energy_combo.setCurrentIndex(3)  # 3
    widget._stress_combo.setCurrentIndex(2)  # 2
    widget.save_entry()

    entry = tmp_db.get_diary_entry("2026-07-03")
    assert entry["content"] == "今天完成了服务层实现"
    assert entry["mood_score"] == 4
    assert entry["mood_emoji"] == "😊"
    assert entry["energy_score"] == 3
    assert entry["stress_score"] == 2
    assert widget._status_label.text() == "已保存"


def test_widget_allows_state_only_save(qapp, tmp_db):
    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")

    widget._mood_combo.setCurrentIndex(2)  # 😐 2
    widget._energy_combo.setCurrentIndex(1)  # 1
    widget.save_entry()

    entry = tmp_db.get_diary_entry("2026-07-03")
    assert entry["content"] == ""
    assert entry["mood_score"] == 2
    assert entry["energy_score"] == 1


def test_widget_auto_saves_dirty_content_on_date_switch(qapp, tmp_db):
    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")
    widget._content_edit.setPlainText("未手动保存的草稿")

    widget.refresh("2026-07-04")

    previous_entry = tmp_db.get_diary_entry("2026-07-03")
    assert previous_entry["content"] == "未手动保存的草稿"
    assert widget._content_edit.toPlainText() == ""


def test_widget_can_insert_basic_html_table(qapp, tmp_db):
    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")

    widget.insert_table(2, 2)

    html = widget._content_edit.toHtml()
    assert "<table" in html.lower()
    assert "<td" in html.lower()
    assert "<tr" in html.lower()


def test_widget_toolbar_exposes_rich_text_actions_and_table_button(qapp, tmp_db):
    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")

    assert widget._format_bar is not None
    assert widget._bold_btn.text() == "加粗"
    assert widget._bullet_btn.text() == "列表"
    assert widget._table_btn.text() == "表格"
    assert widget._table_row_add_btn.text() == "行+"
    assert widget._table_row_remove_btn.text() == "行-"
    assert widget._table_col_add_btn.text() == "列+"
    assert widget._table_col_remove_btn.text() == "列-"
    assert widget._table_width_increase_btn.text() == "宽+"
    assert widget._table_width_decrease_btn.text() == "宽-"
    assert widget._table_merge_btn.text() == "合并"
    assert widget._table_split_btn.text() == "拆分"
    assert widget._image_btn.text() == "图片"

    widget._table_btn.click()

    assert "<table" in widget._content_edit.toHtml().lower()


def test_widget_table_actions_can_add_and_remove_rows_and_columns(qapp, tmp_db):
    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")

    widget.insert_table(2, 2)

    table = widget._content_edit.textCursor().currentTable()
    assert table is not None
    assert table.rows() == 2
    assert table.columns() == 2

    widget._table_row_add_btn.click()
    table = widget._content_edit.textCursor().currentTable()
    assert table is not None
    assert table.rows() == 3

    widget._table_col_add_btn.click()
    table = widget._content_edit.textCursor().currentTable()
    assert table is not None
    assert table.columns() == 3

    widget._table_row_remove_btn.click()
    table = widget._content_edit.textCursor().currentTable()
    assert table is not None
    assert table.rows() == 2

    widget._table_col_remove_btn.click()
    table = widget._content_edit.textCursor().currentTable()
    assert table is not None
    assert table.columns() == 2


def test_widget_table_actions_can_merge_and_split_selected_cells(qapp, tmp_db):
    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")

    widget.insert_table(2, 2)
    table = widget._content_edit.textCursor().currentTable()
    assert table is not None

    start_cursor = table.cellAt(0, 0).firstCursorPosition()
    end_cursor = table.cellAt(0, 1).lastCursorPosition()
    start_cursor.setPosition(end_cursor.position(), QTextCursor.MoveMode.KeepAnchor)
    widget._content_edit.setTextCursor(start_cursor)

    widget._table_merge_btn.click()

    table = widget._content_edit.textCursor().currentTable()
    assert table is not None
    merged_cell = table.cellAt(0, 0)
    assert merged_cell.columnSpan() == 2

    widget._table_split_btn.click()

    table = widget._content_edit.textCursor().currentTable()
    assert table is not None
    split_cell = table.cellAt(0, 0)
    assert split_cell.columnSpan() == 1


def test_widget_table_actions_can_adjust_current_column_width(qapp, tmp_db):
    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")

    widget.insert_table(2, 2)
    table = widget._content_edit.textCursor().currentTable()
    assert table is not None

    before = table.format().columnWidthConstraints()
    assert len(before) == 2
    before_values = [constraint.rawValue() for constraint in before]

    widget._table_width_increase_btn.click()
    table = widget._content_edit.textCursor().currentTable()
    assert table is not None
    widened = table.format().columnWidthConstraints()
    widened_values = [constraint.rawValue() for constraint in widened]
    assert widened_values[0] > before_values[0]
    assert widened_values[1] < before_values[1]

    widget._table_width_decrease_btn.click()
    table = widget._content_edit.textCursor().currentTable()
    assert table is not None
    narrowed = table.format().columnWidthConstraints()
    narrowed_values = [constraint.rawValue() for constraint in narrowed]
    assert narrowed_values[0] < widened_values[0]
    assert "width=" in widget._content_edit.toHtml().lower()


def test_widget_adding_table_column_rebalances_width_constraints(qapp, tmp_db):
    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")

    widget.insert_table(2, 2)
    widget._table_width_increase_btn.click()
    widget._table_col_add_btn.click()

    table = widget._content_edit.textCursor().currentTable()
    assert table is not None

    widths = [constraint.rawValue() for constraint in table.format().columnWidthConstraints()]
    assert len(widths) == 3
    assert round(sum(widths), 3) == 100.0
    assert all(width >= 10.0 for width in widths)


def test_widget_removing_table_column_preserves_existing_width_bias(qapp, tmp_db):
    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")

    widget.insert_table(2, 3)
    widget._table_width_increase_btn.click()
    widget._table_width_increase_btn.click()

    table = widget._content_edit.textCursor().currentTable()
    assert table is not None
    before_remove = [constraint.rawValue() for constraint in table.format().columnWidthConstraints()]
    assert before_remove[0] > before_remove[1]

    third_cell_cursor = table.cellAt(0, 2).firstCursorPosition()
    widget._content_edit.setTextCursor(third_cell_cursor)
    widget._table_col_remove_btn.click()

    table = widget._content_edit.textCursor().currentTable()
    assert table is not None
    widths = [constraint.rawValue() for constraint in table.format().columnWidthConstraints()]
    assert len(widths) == 2
    assert round(sum(widths), 3) == 100.0
    assert widths[0] > widths[1]


def test_widget_persisted_pasted_image_records_attachment_metadata(qapp, tmp_db):
    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")

    image = QImage(12, 12, QImage.Format.Format_ARGB32)
    image.fill(0xFF336699)
    widget._handle_pasted_image(image)

    entry = tmp_db.get_diary_entry("2026-07-03")
    assert entry["attachments_json"]
    assert entry["attachments_json"][0]["path"].endswith(".png")
    assert entry["attachments_json"][0]["path"].startswith(str(tmp_db.data_dir))


def test_widget_editor_paste_image_mimedata_persists_attachment(qapp, tmp_db):
    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")

    image = QImage(14, 14, QImage.Format.Format_ARGB32)
    image.fill(0xFF884422)
    mime = QMimeData()
    mime.setImageData(image)

    assert widget._content_edit.canInsertFromMimeData(mime)
    widget._content_edit.insertFromMimeData(mime)

    entry = tmp_db.get_diary_entry("2026-07-03")
    assert entry["attachments_json"]
    assert "<img" in entry["content_html"].lower()


def test_widget_save_removes_deleted_image_attachment_and_file(qapp, tmp_db):
    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")

    image = QImage(12, 12, QImage.Format.Format_ARGB32)
    image.fill(0xFF336699)
    widget._handle_pasted_image(image)

    saved_entry = tmp_db.get_diary_entry("2026-07-03")
    attachment_path = Path(saved_entry["attachments_json"][0]["path"])
    assert attachment_path.exists()

    widget._content_edit.setPlainText("只保留文字")
    widget.save_entry()

    entry = tmp_db.get_diary_entry("2026-07-03")
    assert entry["attachments_json"] == []
    assert not attachment_path.exists()


def test_widget_accepts_local_image_drop_and_persists_attachment(qapp, tmp_db, tmp_path):
    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")

    image_path = tmp_path / "dropped.png"
    image = QImage(16, 10, QImage.Format.Format_ARGB32)
    image.fill(0xFF2277AA)
    assert image.save(str(image_path))

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(image_path))])

    assert widget._content_edit.canInsertFromMimeData(mime)
    widget._content_edit.insertFromMimeData(mime)

    entry = tmp_db.get_diary_entry("2026-07-03")
    assert entry["attachments_json"]
    assert entry["attachments_json"][0]["path"].endswith(".png")
    assert "<img" in entry["content_html"].lower()


def test_widget_exposes_visible_editor_and_actions_for_daily_writing(qapp, tmp_db):
    widget = DiaryWidget(tmp_db, DummyConfig())
    widget.refresh("2026-07-03")

    assert widget._content_box is not None
    assert widget._content_edit is not None
    assert widget._save_btn is not None
    assert widget._content_edit.placeholderText()
    assert widget._content_edit.minimumHeight() >= 300
    assert widget._summary_box is not None
    assert widget._hint_box is not None
    assert widget._state_box is not None
    assert widget._save_btn.text() == "保存"
    assert widget._mood_combo.count() >= 6
