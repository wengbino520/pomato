import shutil
from pathlib import Path
from uuid import uuid4

from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QFont,
    QImage,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextLength,
    QTextListFormat,
    QTextTableFormat,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
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

_FORMAT_BTN_STYLE = (
    f"QPushButton {{ background:{COLORS['grey_bg']}; color:{COLORS['grey_dark']};"
    f" border:1px solid {COLORS['grey_border']}; border-radius:5px; padding:5px 12px; font-size:12px; }}"
    f"QPushButton:hover {{ border-color:{COLORS['primary']}; color:{COLORS['primary']}; }}"
)

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}


class RichDiaryTextEdit(QTextEdit):
    """允许粘贴图片和富文本的日记编辑器。"""

    def __init__(self, diary_widget, parent=None):
        super().__init__(parent)
        self._diary_widget = diary_widget

    @staticmethod
    def _extract_local_image_paths(source) -> list[Path]:
        image_paths: list[Path] = []
        if source is None or not source.hasUrls():
            return image_paths
        for url in source.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.suffix.lower() in _IMAGE_EXTENSIONS:
                image_paths.append(path)
        return image_paths

    def canInsertFromMimeData(self, source):
        if source is not None and source.hasImage():
            return True
        if self._extract_local_image_paths(source):
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source is not None and source.hasImage():
            image = source.imageData()
            if isinstance(image, QImage):
                if hasattr(self._diary_widget, "_handle_pasted_image"):
                    self._diary_widget._handle_pasted_image(image)
                    return
            super().insertFromMimeData(source)
            return
        image_paths = self._extract_local_image_paths(source)
        if image_paths and hasattr(self._diary_widget, "_handle_dropped_image_file"):
            inserted_any = False
            for path in image_paths:
                inserted_any = self._diary_widget._handle_dropped_image_file(path) or inserted_any
            if inserted_any:
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

        self._format_bar = QFrame()
        format_layout = QHBoxLayout(self._format_bar)
        format_layout.setContentsMargins(0, 0, 0, 0)
        format_layout.setSpacing(8)

        self._bold_btn = self._make_format_button("加粗", self._toggle_bold)
        self._bullet_btn = self._make_format_button("列表", self._insert_bullet_list)
        self._quote_btn = self._make_format_button("引用", self._insert_quote_block)
        self._table_btn = self._make_format_button("表格", self._on_insert_table)
        self._table_row_add_btn = self._make_format_button("行+", self._insert_table_row)
        self._table_row_remove_btn = self._make_format_button("行-", self._remove_table_row)
        self._table_col_add_btn = self._make_format_button("列+", self._insert_table_column)
        self._table_col_remove_btn = self._make_format_button("列-", self._remove_table_column)
        self._table_width_increase_btn = self._make_format_button("宽+", self._increase_table_column_width)
        self._table_width_decrease_btn = self._make_format_button("宽-", self._decrease_table_column_width)
        self._table_merge_btn = self._make_format_button("合并", self._merge_table_cells)
        self._table_split_btn = self._make_format_button("拆分", self._split_table_cell)
        self._image_btn = self._make_format_button("图片", self._on_insert_image)

        for button in (
            self._bold_btn,
            self._bullet_btn,
            self._quote_btn,
            self._table_btn,
            self._table_row_add_btn,
            self._table_row_remove_btn,
            self._table_col_add_btn,
            self._table_col_remove_btn,
            self._table_width_increase_btn,
            self._table_width_decrease_btn,
            self._table_merge_btn,
            self._table_split_btn,
            self._image_btn,
        ):
            format_layout.addWidget(button)
        format_layout.addStretch()
        content_layout.addWidget(self._format_bar)

        self._content_edit = RichDiaryTextEdit(self, self._content_box)
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
        cursor = self._content_edit.textCursor()
        table_format = QTextTableFormat()
        table_format.setBorder(1)
        table_format.setCellPadding(4)
        table_format.setCellSpacing(0)
        table_format.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
        table_format.setBorderStyle(QTextTableFormat.BorderStyle.BorderStyle_Solid)
        table_format.setColumnWidthConstraints(self._build_equal_width_constraints(cols))
        table = cursor.insertTable(rows, cols, table_format)
        self._focus_table_cell(table, 0, 0)
        block_format = QTextBlockFormat()
        block_format.setTopMargin(6)
        block_format.setBottomMargin(6)
        end_cursor = table.lastCursorPosition()
        end_cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        end_cursor.insertBlock(block_format)
        self._content_edit.setTextCursor(table.cellAt(0, 0).firstCursorPosition())

    def _make_format_button(self, text: str, handler):
        button = QPushButton(text)
        button.setStyleSheet(_FORMAT_BTN_STYLE)
        button.clicked.connect(handler)
        return button

    def _toggle_bold(self):
        cursor = self._content_edit.textCursor()
        current_weight = cursor.charFormat().fontWeight()
        next_weight = QFont.Weight.Normal if current_weight >= QFont.Weight.Bold else QFont.Weight.Bold
        format_state = QTextCharFormat()
        format_state.setFontWeight(next_weight)
        cursor.mergeCharFormat(format_state)
        self._content_edit.mergeCurrentCharFormat(format_state)

    def _insert_bullet_list(self):
        cursor = self._content_edit.textCursor()
        cursor.insertList(QTextListFormat.Style.ListDisc)

    def _insert_quote_block(self):
        cursor = self._content_edit.textCursor()
        if cursor.hasSelection():
            quoted_text = cursor.selectedText().replace("\u2029", "<br>")
            cursor.insertHtml(
                f"<blockquote style='margin:8px 0;padding-left:12px;border-left:3px solid {COLORS['primary_light']};color:{COLORS['grey_medium']};'>{quoted_text}</blockquote>"
            )
            return
        cursor.insertHtml(
            f"<blockquote style='margin:8px 0;padding-left:12px;border-left:3px solid {COLORS['primary_light']};color:{COLORS['grey_medium']};'>引用内容</blockquote><p></p>"
        )
        self._content_edit.moveCursor(QTextCursor.MoveOperation.End)

    def _on_insert_table(self):
        self.insert_table()

    def _current_table_context(self):
        cursor = self._content_edit.textCursor()
        table = cursor.currentTable()
        if table is None:
            return None, None
        cell = table.cellAt(cursor)
        if not cell.isValid():
            return table, None
        return table, cell

    def _focus_table_cell(self, table, row: int, column: int):
        if table is None or table.rows() <= 0 or table.columns() <= 0:
            return
        target_row = max(0, min(row, table.rows() - 1))
        target_col = max(0, min(column, table.columns() - 1))
        cell = table.cellAt(target_row, target_col)
        if cell.isValid():
            self._content_edit.setTextCursor(cell.firstCursorPosition())

    @staticmethod
    def _build_equal_width_constraints(column_count: int) -> list[QTextLength]:
        if column_count <= 0:
            return []
        base_width = 100.0 / column_count
        return [QTextLength(QTextLength.Type.PercentageLength, base_width) for _ in range(column_count)]

    @classmethod
    def _normalize_table_widths(cls, widths: list[float]) -> list[float]:
        if not widths:
            return []
        positive_widths = [max(0.0, float(width)) for width in widths]
        total = sum(positive_widths)
        if total <= 0:
            return cls._build_equal_widths(len(positive_widths))
        return [(width / total) * 100.0 for width in positive_widths]

    @classmethod
    def _build_widths_after_column_insert(cls, widths: list[float], insert_at: int) -> list[float]:
        if not widths:
            return [100.0]

        normalized = cls._normalize_table_widths(widths)
        donor_index = min(max(insert_at - 1, 0), len(normalized) - 1)
        donor_width = normalized[donor_index]
        new_width = donor_width / 2.0
        normalized[donor_index] = donor_width - new_width
        normalized.insert(insert_at, new_width)
        return cls._normalize_table_widths(normalized)

    @classmethod
    def _build_widths_after_column_remove(cls, widths: list[float], remove_at: int) -> list[float]:
        if len(widths) <= 1:
            return []

        normalized = cls._normalize_table_widths(widths)
        target_index = remove_at if 0 <= remove_at < len(normalized) else len(normalized) - 1
        remaining = [width for index, width in enumerate(normalized) if index != target_index]
        return cls._normalize_table_widths(remaining)

    def _get_table_width_values(self, table) -> list[float]:
        constraints = list(table.format().columnWidthConstraints())
        column_count = table.columns()
        if len(constraints) != column_count:
            return [100.0 / column_count for _ in range(column_count)]

        values = [max(0.0, float(constraint.value(100.0))) for constraint in constraints]
        normalized = self._normalize_table_widths(values)
        if not normalized:
            return [100.0 / column_count for _ in range(column_count)]
        return normalized

    def _set_table_width_values(self, table, widths: list[float]):
        if table is None or not widths:
            return
        table_format = table.format()
        constraints = [QTextLength(QTextLength.Type.PercentageLength, width) for width in widths]
        table_format.setColumnWidthConstraints(constraints)
        table.setFormat(table_format)

    def _adjust_current_column_width(self, delta: float):
        table, cell = self._current_table_context()
        if table is None or cell is None or table.columns() <= 1:
            return

        widths = self._get_table_width_values(table)
        target_index = cell.column()
        other_indexes = [index for index in range(len(widths)) if index != target_index]
        min_width = 10.0

        if delta > 0:
            available = sum(max(0.0, widths[index] - min_width) for index in other_indexes)
            actual_delta = min(delta, available)
        else:
            actual_delta = max(delta, min_width - widths[target_index])

        if abs(actual_delta) < 0.01:
            return

        widths[target_index] += actual_delta
        share = actual_delta / len(other_indexes)
        for index in other_indexes:
            widths[index] -= share

        # Clamp and renormalize to avoid negative drift from rounding.
        widths = [max(min_width, width) for width in widths]
        widths = self._normalize_table_widths(widths)
        self._set_table_width_values(table, widths)
        self._focus_table_cell(table, cell.row(), min(target_index, table.columns() - 1))
        self._mark_dirty()

    def _insert_table_row(self):
        table, cell = self._current_table_context()
        if table is None:
            return
        row = cell.row() if cell else table.rows() - 1
        column = cell.column() if cell else 0
        insert_at = row + 1
        table.insertRows(insert_at, 1)
        self._focus_table_cell(table, insert_at, column)
        self._mark_dirty()

    def _remove_table_row(self):
        table, cell = self._current_table_context()
        if table is None or table.rows() <= 1:
            return
        row = cell.row() if cell else table.rows() - 1
        column = cell.column() if cell else 0
        target_row = row - 1 if row == table.rows() - 1 else row
        table.removeRows(row, 1)
        self._focus_table_cell(table, target_row, column)
        self._mark_dirty()

    def _insert_table_column(self):
        table, cell = self._current_table_context()
        if table is None:
            return
        widths = self._get_table_width_values(table)
        row = cell.row() if cell else 0
        column = cell.column() if cell else table.columns() - 1
        insert_at = column + 1
        table.insertColumns(insert_at, 1)
        self._set_table_width_values(table, self._build_widths_after_column_insert(widths, insert_at))
        self._focus_table_cell(table, row, insert_at)
        self._mark_dirty()

    def _remove_table_column(self):
        table, cell = self._current_table_context()
        if table is None or table.columns() <= 1:
            return
        widths = self._get_table_width_values(table)
        row = cell.row() if cell else 0
        column = cell.column() if cell else table.columns() - 1
        target_col = column - 1 if column == table.columns() - 1 else column
        table.removeColumns(column, 1)
        self._set_table_width_values(table, self._build_widths_after_column_remove(widths, column))
        self._focus_table_cell(table, row, target_col)
        self._mark_dirty()

    @staticmethod
    def _build_equal_widths(column_count: int) -> list[float]:
        if column_count <= 0:
            return []
        width = 100.0 / column_count
        return [width for _ in range(column_count)]

    def _increase_table_column_width(self):
        self._adjust_current_column_width(10.0)

    def _decrease_table_column_width(self):
        self._adjust_current_column_width(-10.0)

    def _merge_table_cells(self):
        cursor = self._content_edit.textCursor()
        table = cursor.currentTable()
        if table is None or not cursor.hasSelection():
            return
        table.mergeCells(cursor)
        self._mark_dirty()

    def _split_table_cell(self):
        table, cell = self._current_table_context()
        if table is None or cell is None:
            return
        if cell.rowSpan() <= 1 and cell.columnSpan() <= 1:
            return
        table.splitCell(cell.row(), cell.column(), 1, 1)
        self._focus_table_cell(table, cell.row(), cell.column())
        self._mark_dirty()

    def _on_insert_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            str(self.db.data_dir),
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)",
        )
        if path:
            self._handle_dropped_image_file(Path(path))

    def _handle_pasted_image(self, image: QImage):
        self._insert_image(image)

    def _handle_dropped_image_file(self, image_path: Path) -> bool:
        if not image_path.exists() or image_path.suffix.lower() not in _IMAGE_EXTENSIONS:
            return False
        self._insert_image_file(image_path)
        return True

    def _insert_image(self, image: QImage, display_name: str | None = None):
        if image.isNull():
            return
        if not self._current_date:
            return
        target_dir = self.db.data_dir / "diary_attachments" / self._current_date
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = f"img_{uuid4().hex[:12]}.png"
        path = target_dir / filename
        image.save(str(path), "PNG")
        self._append_image_attachment(path, display_name or filename, mime_type="image/png")

    def _insert_image_file(self, image_path: Path):
        if not self._current_date:
            return
        target_dir = self.db.data_dir / "diary_attachments" / self._current_date
        target_dir.mkdir(parents=True, exist_ok=True)
        suffix = image_path.suffix.lower() or ".png"
        filename = f"img_{uuid4().hex[:12]}{suffix}"
        target_path = target_dir / filename
        shutil.copy2(image_path, target_path)
        mime_type = f"image/{suffix.lstrip('.')}" if suffix != ".jpg" else "image/jpeg"
        self._append_image_attachment(target_path, image_path.name, mime_type=mime_type)

    def _append_image_attachment(self, image_path: Path, display_name: str, *, mime_type: str):
        attachment = {
            "id": image_path.name,
            "path": str(image_path),
            "name": display_name,
            "mime_type": mime_type,
        }
        if not any(existing.get("path") == attachment["path"] for existing in self._attachments_json):
            self._attachments_json.append(attachment)
        self._content_edit.insertHtml(f'<img src="{image_path.as_posix()}" width="320"/>')
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
