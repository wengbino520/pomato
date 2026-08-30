from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.services.diary_service import DiaryService
from src.services.logger import get_logger

logger = get_logger(__name__)

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}


class DiaryHistoryWindow(QDialog):
    def __init__(self, db, config, parent=None, initial_date=None, on_open_date=None):
        super().__init__(parent)
        self.db = db
        self.config = config
        self.service = DiaryService(db, config)
        self._initial_date = initial_date
        self._on_open_date = on_open_date
        self._current_date: str | None = None
        self.setWindowTitle("POMATO · 日记历史")
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(840, 560)
        self._setup_ui()
        self._load_items()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()
        header.setStyleSheet("background:#ef5350;")
        header.setFixedHeight(48)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 8, 16, 8)
        title = QLabel("📓  日记历史")
        title.setStyleSheet("color:white; font-size:16px; font-weight:bold;")
        hl.addWidget(title)
        hl.addStretch()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索日期、正文或附件…")
        self.search_input.setStyleSheet(
            "QLineEdit{background:white;color:#333;border:none;border-radius:4px;padding:6px 10px;min-width:200px;}"
        )
        self.search_input.textChanged.connect(self._load_items)
        hl.addWidget(self.search_input)
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(8, 8, 4, 8)
        ll.addWidget(QLabel("日期列表"))
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget{border:1px solid #eee;border-radius:4px;}"
            "QListWidget::item{padding:8px 10px;}"
            "QListWidget::item:selected{background:#ffebee;color:#d32f2f;}"
        )
        self.list_widget.currentItemChanged.connect(self._on_item_changed)
        ll.addWidget(self.list_widget)
        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 8, 8, 8)

        self.preview_title = QLabel("请选择左侧日期查看日记")
        self.preview_title.setStyleSheet("font-weight:bold; color:#333;")
        rl.addWidget(self.preview_title)

        self.preview_meta = QLabel("")
        self.preview_meta.setWordWrap(True)
        self.preview_meta.setStyleSheet("color:#666; font-size:12px;")
        rl.addWidget(self.preview_meta)

        self.preview_context = QLabel("")
        self.preview_context.setWordWrap(True)
        self.preview_context.setStyleSheet("color:#666; font-size:12px;")
        rl.addWidget(self.preview_context)

        self.preview_content = QTextEdit()
        self.preview_content.setReadOnly(True)
        self.preview_content.setStyleSheet(
            "QTextEdit{border:1px solid #eee;border-radius:4px;"
            "font-family:Consolas,'Microsoft YaHei';font-size:13px;}"
        )
        rl.addWidget(self.preview_content, 1)

        self.preview_attachments = QListWidget()
        self.preview_attachments.setMaximumHeight(120)
        self.preview_attachments.setIconSize(QSize(44, 44))
        self.preview_attachments.setStyleSheet(
            "QListWidget{border:1px solid #eee;border-radius:4px;}"
            "QListWidget::item{padding:6px 10px;}"
        )
        self.preview_attachments.itemDoubleClicked.connect(self._open_attachment_item)
        rl.addWidget(QLabel("附件"))
        rl.addWidget(self.preview_attachments)

        splitter.addWidget(right)
        splitter.setSizes([260, 580])

        layout.addWidget(splitter, 1)

        bottom = QHBoxLayout()
        self.open_btn = QPushButton("打开该日期到主窗口")
        self.open_btn.clicked.connect(self._open_selected_date)
        self.open_btn.setEnabled(False)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(self.open_btn)
        bottom.addStretch()
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def _load_items(self):
        self.list_widget.clear()
        items = self._filter_items(self.db.get_diary_list_items())
        if not items:
            placeholder_text = "（暂无日记记录）" if not self.search_input.text().strip() else "（未找到匹配的日记）"
            placeholder = QListWidgetItem(placeholder_text)
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(placeholder)
            self._current_date = None
            self.open_btn.setEnabled(False)
            self._reset_preview("未找到可预览的日记" if self.search_input.text().strip() else "请选择左侧日期查看日记")
            return

        target_date = self._current_date or self._initial_date
        selected_row = 0
        for index, item in enumerate(items):
            list_item = QListWidgetItem(self._format_list_item(item))
            list_item.setData(Qt.ItemDataRole.UserRole, item["entry_date"])
            self.list_widget.addItem(list_item)
            if item["entry_date"] == target_date:
                selected_row = index

        self.list_widget.setCurrentRow(selected_row)
        self._initial_date = None

    def _filter_items(self, items: list[dict]) -> list[dict]:
        keyword = self.search_input.text().strip().lower()
        if not keyword:
            return items

        filtered_items: list[dict] = []
        for item in items:
            attachment_names = " ".join(
                (attachment.get("name") or attachment.get("path") or "")
                for attachment in item.get("attachments_json") or []
            )
            haystack = " ".join(
                [
                    item.get("entry_date") or "",
                    item.get("content") or "",
                    item.get("content_html") or "",
                    attachment_names,
                ]
            ).lower()
            if keyword in haystack:
                filtered_items.append(item)
        return filtered_items

    @staticmethod
    def _format_list_item(item: dict) -> str:
        mood = item.get("mood_emoji") or "○"
        word_count = item.get("word_count") or 0
        updated_at = item.get("updated_at") or ""
        updated_text = updated_at[11:16] if len(updated_at) >= 16 else "--:--"
        content_state = f"{word_count}字" if item.get("has_content") else "无内容"
        return f"{item['entry_date']}  {mood}  {content_state}  {updated_text}"

    def _on_item_changed(self, current, _previous):
        if current is None:
            return
        date_str = current.data(Qt.ItemDataRole.UserRole)
        if not date_str:
            self.open_btn.setEnabled(False)
            return
        self._current_date = date_str
        self.open_btn.setEnabled(True)
        self._refresh_preview(date_str)

    def _refresh_preview(self, date_str: str):
        entry = self.db.get_diary_entry(date_str) or {}
        context = self.service.get_daily_context(date_str)
        self.preview_title.setText(f"📓  {date_str}")
        self.preview_meta.setText(
            f"情绪：{entry.get('mood_emoji') or '未记录'}  /  "
            f"精力：{entry.get('energy_score') or '未记录'}  /  "
            f"压力：{entry.get('stress_score') or '未记录'}  /  "
            f"字数：{entry.get('word_count') or 0}"
        )
        self.preview_context.setText(
            f"今日速览：🍅 {context['pomodoro_count']} 个番茄  ·  "
            f"⏱ {context['focus_minutes']} 分钟  ·  "
            f"✅ 待办 {context['todo_done']}/{context['todo_total']}\n"
            f"最后更新：{(entry.get('updated_at') or '').replace('T', ' ')[:16] or '未保存'}"
        )
        html_content = entry.get("content_html") or ""
        if html_content.strip():
            self.preview_content.setHtml(html_content)
        else:
            self.preview_content.setPlainText(entry.get("content") or "（仅状态记录，无正文内容）")
        self._render_attachments(entry.get("attachments_json") or [])

    def _reset_preview(self, title: str):
        self.preview_title.setText(title)
        self.preview_meta.setText("")
        self.preview_context.setText("")
        self.preview_content.clear()
        self._render_attachments([])

    def _render_attachments(self, attachments):
        self.preview_attachments.clear()
        if not attachments:
            item = QListWidgetItem("（无附件）")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.preview_attachments.addItem(item)
            return
        for attachment in attachments:
            name = attachment.get("name") or attachment.get("id") or "附件"
            attachment_path = self._resolve_attachment_path(attachment.get("path") or "")
            display_name = name
            if not attachment_path.exists():
                display_name = f"{name}（文件缺失）"
            item = QListWidgetItem(name)
            item.setText(display_name)
            item.setData(Qt.ItemDataRole.UserRole, str(attachment_path))
            item.setToolTip(str(attachment_path))
            if attachment_path.exists() and attachment_path.suffix.lower() in _IMAGE_EXTENSIONS:
                pixmap = QPixmap(str(attachment_path))
                if not pixmap.isNull():
                    thumbnail = pixmap.scaled(
                        44,
                        44,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    item.setIcon(QIcon(thumbnail))
            self.preview_attachments.addItem(item)

    def _resolve_attachment_path(self, path_value: str) -> Path:
        attachment_path = Path(path_value)
        if attachment_path.is_absolute():
            return attachment_path
        return self.db.data_dir / attachment_path

    def _open_attachment_item(self, item):
        path_value = item.data(Qt.ItemDataRole.UserRole)
        if not path_value:
            return

        attachment_path = Path(path_value)
        if not attachment_path.is_absolute():
            attachment_path = self.db.data_dir / attachment_path
        if not attachment_path.exists():
            logger.debug("Diary attachment does not exist: %s", attachment_path)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(attachment_path)))

    def _open_selected_date(self):
        if self._current_date and self._on_open_date:
            self._on_open_date(self._current_date)
            self.accept()