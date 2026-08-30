from PyQt6.QtGui import QImage

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
