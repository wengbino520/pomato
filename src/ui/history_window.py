from PyQt6.QtCore import Qt
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


class HistoryWindow(QDialog):
    """历史日报列表：左侧日期列表，右侧预览日报内容。"""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._report_by_date: dict[str, dict] = {}
        self.setWindowTitle("POMATO · 历史日报")
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(760, 520)
        self._setup_ui()
        self._load_dates()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── header ─────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet("background:#ef5350;")
        header.setFixedHeight(48)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 8, 16, 8)
        title = QLabel("📚  历史日报")
        title.setStyleSheet("color:white; font-size:16px; font-weight:bold;")
        hl.addWidget(title)
        hl.addStretch()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索日期或内容…")
        self.search_input.setStyleSheet(
            "QLineEdit{background:white;color:#333;border:none;border-radius:4px;padding:6px 10px;min-width:220px;}"
        )
        self.search_input.textChanged.connect(self._load_dates)
        hl.addWidget(self.search_input)
        layout.addWidget(header)

        # ── splitter ───────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: date list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(8, 8, 4, 8)
        ll.addWidget(QLabel("日报列表"))

        self.date_list = QListWidget()
        self.date_list.setStyleSheet(
            "QListWidget { border:1px solid #eee; border-radius:4px; }"
            "QListWidget::item { padding:8px; }"
            "QListWidget::item:selected { background:#ffebee; color:#d32f2f; }"
        )
        self.date_list.currentItemChanged.connect(self._on_date_selected)
        ll.addWidget(self.date_list)
        splitter.addWidget(left)

        # Right: report preview
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 8, 8, 8)

        top_bar = QHBoxLayout()
        self.preview_title = QLabel("请选择左侧日期查看日报")
        self.preview_title.setStyleSheet("font-weight:bold; color:#333;")
        top_bar.addWidget(self.preview_title)
        top_bar.addStretch()

        copy_btn = QPushButton("复制")
        copy_btn.setStyleSheet(
            "QPushButton{border:1px solid #ddd;border-radius:4px;padding:4px 12px;}"
            "QPushButton:hover{background:#f5f5f5;}"
        )
        copy_btn.clicked.connect(self._copy_current)
        top_bar.addWidget(copy_btn)
        rl.addLayout(top_bar)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setStyleSheet(
            "QTextEdit{border:1px solid #eee;border-radius:4px;"
            "font-family:Consolas,'Microsoft YaHei';font-size:13px;}"
        )
        rl.addWidget(self.preview)
        splitter.addWidget(right)

        splitter.setSizes([200, 560])
        layout.addWidget(splitter, 1)

    def _load_dates(self):
        self.date_list.clear()
        self._report_by_date = {}

        keyword = self.search_input.text().strip()
        reports = self.db.search_reports(keyword)
        if not reports:
            item = QListWidgetItem("（暂无历史日报）")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.date_list.addItem(item)
            self.preview_title.setText("请选择左侧日期查看日报")
            self.preview.setPlainText("")
            return

        for report in reports:
            d = report.get("date")
            if not d:
                continue
            self._report_by_date[d] = report
            self.date_list.addItem(QListWidgetItem(d))
        self.date_list.setCurrentRow(0)

    def _on_date_selected(self, current: QListWidgetItem, _prev):
        if current is None:
            return
        date_str = current.text()
        report = self._report_by_date.get(date_str)
        if report is None:
            report = self.db.get_report(date_str)
        if not report:
            self.preview.setPlainText("（无内容）")
            return
        self.preview_title.setText(f"📄  {date_str}")
        content = report.get("final_report") or report.get("ai_summary") or ""
        if not content:
            # Fall back to raw entries list
            lines = [f"- {e.get('start_time','')[:5]}-{e.get('end_time','')[:5]}  {e.get('content','')}"
                     for e in (report.get("raw_entries") or [])
                     if not e.get("skipped")]
            content = "\n".join(lines) or "（无内容）"
        self.preview.setPlainText(content)

    def _copy_current(self):
        from PyQt6.QtWidgets import QApplication
        text = self.preview.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
