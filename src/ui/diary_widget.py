from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.services.diary_service import DiaryService
from src.services.logger import get_logger
from src.ui.styles import COLORS, STYLES

logger = get_logger(__name__)

_MOOD_OPTIONS = [
    ("未选择", None),
    ("😞 1", (1, "😞")),
    ("😐 2", (2, "😐")),
    ("🙂 3", (3, "🙂")),
    ("😊 4", (4, "😊")),
    ("😄 5", (5, "😄")),
]

_SCORE_OPTIONS = [("未选择", None)] + [(str(score), score) for score in range(1, 6)]

_CARD_STYLE = (
    f"QFrame {{ background:{COLORS['white']}; border:1px solid {COLORS['grey_border_light']};"
    f" border-radius:8px; }}"
)


class RichDiaryTextEdit(QTextEdit):
    """允许粘贴图片和富文本的日记编辑器。"""

    def canInsertFromMimeData(self, source):
        if source is not None and source.hasImage():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source is not None and source.hasImage():
            image = source.imageData()
            if isinstance(image, QImage):
                if hasattr(self.parent(), "_handle_pasted_image"):
                    self.parent()._handle_pasted_image(image)
                    return
            super().insertFromMimeData(source)
            return
        super().insertFromMimeData(source)


class DiaryWidget(QWidget):
    """主窗口中的日记页组件。"""

    def __init__(self, db, config, diary_service=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.config = config
        self.service = diary_service or DiaryService(db, config)
        self._current_date: str | None = None
        self._loading = False
        self._dirty = False
        self._attachments_json: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        self._date_label = QLabel("📓 日记")
        self._date_label.setStyleSheet(f"font-size:16px; font-weight:bold; color:{COLORS['grey_dark']};")
        root.addWidget(self._date_label)

        body = QHBoxLayout()
        body.setSpacing(14)
        root.addLayout(body, 1)

        left_col = QVBoxLayout()
        left_col.setSpacing(0)
        right_col = QVBoxLayout()
        right_col.setSpacing(14)

        body.addLayout(left_col, 3)
        body.addLayout(right_col, 2)

        self._content_box = QFrame()
        self._content_box.setStyleSheet(_CARD_STYLE)
        content_layout = QVBoxLayout(self._content_box)
        content_layout.setContentsMargins(16, 14, 16, 14)
        content_layout.setSpacing(10)

        content_title = QLabel("日记内容")
        content_title.setStyleSheet(f"font-size:13px; font-weight:bold; color:{COLORS['grey_dark']};")
        content_layout.addWidget(content_title)

        self._content_edit = RichDiaryTextEdit(self)
        self._content_edit.setAcceptRichText(True)
        self._content_edit.setStyleSheet(STYLES["text_edit"])
        self._content_edit.setPlaceholderText("写下今天的工作、状态或任何值得记录的片段……")
        self._content_edit.setMinimumHeight(360)
        self._content_edit.textChanged.connect(self._mark_dirty)
        content_layout.addWidget(self._content_edit, 1)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"font-size:12px; color:{COLORS['grey_medium']};")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 2, 0, 0)
        actions.addWidget(self._status_label, 1)
        actions.addStretch()
        self._save_btn = QPushButton("保存")
        self._save_btn.setStyleSheet(STYLES["btn_primary"])
        self._save_btn.clicked.connect(self.save_entry)
        actions.addWidget(self._save_btn)
        content_layout.addLayout(actions)

        left_col.addWidget(self._content_box, 1)

        self._summary_box = QFrame()
        self._summary_box.setStyleSheet(_CARD_STYLE)
        self._summary_box.setMinimumHeight(92)
        summary_layout = QVBoxLayout(self._summary_box)
        summary_layout.setContentsMargins(16, 14, 16, 14)
        summary_layout.setSpacing(10)
        self._summary_title = QLabel("今日速览")
        self._summary_title.setStyleSheet(f"font-size:13px; font-weight:bold; color:{COLORS['grey_dark']};")
        self._summary_label = QLabel("")
        self._summary_label.setWordWrap(True)
        self._summary_label.setStyleSheet(f"font-size:12px; color:{COLORS['grey_medium']};")
        self._summary_label.setMinimumHeight(22)
        summary_layout.addWidget(self._summary_title)
        summary_layout.addWidget(self._summary_label)
        right_col.addWidget(self._summary_box)

        self._hint_box = QFrame()
        self._hint_box.setStyleSheet(_CARD_STYLE)
        self._hint_box.setMinimumHeight(108)
        hint_layout = QVBoxLayout(self._hint_box)
        hint_layout.setContentsMargins(16, 14, 16, 14)
        hint_layout.setSpacing(10)
        hint_title = QLabel("写作提示")
        hint_title.setStyleSheet(f"font-size:13px; font-weight:bold; color:{COLORS['grey_dark']};")
        self._hint_label = QLabel("")
        self._hint_label.setWordWrap(True)
        self._hint_label.setStyleSheet(f"font-size:13px; color:{COLORS['grey_medium']};")
        self._hint_label.setMinimumHeight(68)
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        hint_layout.addWidget(hint_title)
        hint_layout.addWidget(self._hint_label)
        right_col.addWidget(self._hint_box)

        self._state_box = QFrame()
        self._state_box.setStyleSheet(_CARD_STYLE)
        self._state_box.setMinimumHeight(148)
        state_layout = QVBoxLayout(self._state_box)
        state_layout.setContentsMargins(16, 14, 16, 14)
        state_layout.setSpacing(12)
        state_title = QLabel("今日状态")
        state_title.setStyleSheet(f"font-size:13px; font-weight:bold; color:{COLORS['grey_dark']};")
        state_layout.addWidget(state_title)
        state_layout.addLayout(self._build_state_row("情绪", "mood"))
        state_layout.addLayout(self._build_state_row("精力", "energy"))
        state_layout.addLayout(self._build_state_row("压力", "stress"))
        right_col.addWidget(self._state_box)
        right_col.addStretch()

    def _build_state_row(self, label_text: str, kind: str):
        row = QHBoxLayout()
        row.setSpacing(10)
        label = QLabel(f"{label_text}：")
        label.setStyleSheet(f"font-size:12px; color:{COLORS['grey_medium']};")
        label.setMinimumWidth(42)
        combo = QComboBox()
        combo.setStyleSheet(
            "QComboBox { border:1px solid #ddd; border-radius:4px; padding:4px 8px; font-size:12px; min-height:28px; }"
        )
        combo.setMinimumWidth(110)
        options = _MOOD_OPTIONS if kind == "mood" else _SCORE_OPTIONS
        for text, data in options:
            combo.addItem(text, data)
        combo.currentIndexChanged.connect(self._mark_dirty)
        row.addWidget(label)
        row.addWidget(combo)
        row.addStretch()

        if kind == "mood":
            self._mood_combo = combo
        elif kind == "energy":
            self._energy_combo = combo
        else:
            self._stress_combo = combo
        return row

    def refresh(self, date_str: str):
        if self._current_date and self._current_date != date_str and self._dirty:
            self.save_entry(silent=True)

        self._current_date = date_str
        context = self.service.get_daily_context(date_str)
        hints = self.service.get_diary_prompt_hints(date_str)

        self._loading = True
        self._attachments_json = list(context.get("attachments_json") or [])
        self._date_label.setText(f"📓 日记  {date_str}")
        self._summary_label.setText(self._build_summary_text(context))
        self._hint_label.setText(self._build_hint_text(hints))
        html_content = context.get("content_html") or ""
        if html_content.strip():
            self._content_edit.setHtml(html_content)
        else:
            self._content_edit.setPlainText(context["content"])
        self._set_state_value(self._mood_combo, self._find_mood_data(context))
        self._set_state_value(self._energy_combo, context["energy_score"])
        self._set_state_value(self._stress_combo, context["stress_score"])
        self._status_label.setText(self._build_status_text(context))
        self._loading = False
        self._dirty = False

    def insert_table(self, rows: int = 2, cols: int = 2):
        table_html = "<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse; width:100%;'>"
        for _ in range(rows):
            table_html += "<tr>"
            for _ in range(cols):
                table_html += "<td> </td>"
            table_html += "</tr>"
        table_html += "</table><br>"
        self._content_edit.insertHtml(table_html)

    def _handle_pasted_image(self, image: QImage):
        if image.isNull():
            return
        if not self._current_date:
            return
        target_dir = self.db.data_dir / "diary_attachments" / self._current_date
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = f"paste_{abs(hash((self._current_date, image.width(), image.height(), image.text())))}.png"
        path = target_dir / filename
        image.save(str(path))
        attachment = {"id": filename, "path": str(path), "name": filename, "mime_type": "image/png"}
        if not any(existing.get("path") == attachment["path"] for existing in self._attachments_json):
            self._attachments_json.append(attachment)
        self._content_edit.insertHtml(f'<img src="{path.as_posix()}" width="320"/>')
        self._mark_dirty()
        self.save_entry(silent=True)

    def save_entry(self, silent: bool = False):
        if not self._current_date:
            return None
        payload = self._collect_payload()
        entry = self.service.save_diary_entry(self._current_date, **payload)
        self._dirty = False
        if not silent:
            self._status_label.setText("已保存")
        else:
            self._status_label.setText("已自动保存")
        logger.debug("Diary entry saved for %s", self._current_date)
        return entry

    def _collect_payload(self) -> dict:
        mood_data = self._mood_combo.currentData()
        mood_score = mood_data[0] if mood_data else None
        mood_emoji = mood_data[1] if mood_data else None
        html_content = self._content_edit.toHtml()
        plain_content = self._content_edit.toPlainText()
        return {
            "content": plain_content,
            "content_html": html_content,
            "attachments_json": self._attachments_json,
            "mood_score": mood_score,
            "mood_emoji": mood_emoji,
            "energy_score": self._energy_combo.currentData(),
            "stress_score": self._stress_combo.currentData(),
        }

    def _find_mood_data(self, context: dict):
        if context["mood_score"] is None:
            return None
        return (context["mood_score"], context["mood_emoji"])

    def _set_state_value(self, combo: QComboBox, value):
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0)

    def _build_summary_text(self, context: dict) -> str:
        if not context["has_work_data"]:
            return "今天还没有番茄记录或待办数据，可以先记下当前状态或一点想法。"
        return (
            f"🍅 {context['pomodoro_count']} 个番茄  ·  "
            f"⏱ {context['focus_minutes']} 分钟  ·  "
            f"✅ 待办 {context['todo_done']}/{context['todo_total']}"
        )

    @staticmethod
    def _build_hint_text(hints: list[str]) -> str:
        items = "".join(
            f"<div style='margin:0 0 8px 0;'>• {hint}</div>" for hint in hints
        )
        return f"<div style='line-height:1.5;'>{items}</div>"

    def _build_status_text(self, context: dict) -> str:
        if not context["diary_exists"]:
            return "尚未保存本日记。"
        if context["updated_at"]:
            return f"上次保存：{context['updated_at'][:16].replace('T', ' ')}"
        return "已加载历史日记。"

    def _mark_dirty(self, *_args):
        if self._loading:
            return
        self._dirty = True
        self._status_label.setText("有未保存修改")
