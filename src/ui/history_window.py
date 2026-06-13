from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.services.ai_client import AIClient
from src.services.logger import get_logger

logger = get_logger(__name__)


class _HistoryAIWorker(QThread):
    chunk_received = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, ai_client: AIClient, entries: list[dict], report_date: str,
                 todos: list[dict] | None = None):
        super().__init__()
        self.ai_client = ai_client
        self.entries = entries
        self.report_date = report_date
        self.todos = todos or []

    def run(self):
        try:
            result = self.ai_client.generate_report(
                self.entries,
                self.report_date,
                on_chunk=lambda c: self.chunk_received.emit(c),
                todos=self.todos if self.todos else None,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class HistoryWindow(QDialog):
    """历史日报列表：左侧日期列表，右侧预览日报内容，支持 AI 总结。"""

    def __init__(self, db, parent=None, ai_client=None, config=None, initial_date=None):
        super().__init__(parent)
        self.db = db
        self.ai_client = ai_client
        self.config = config or {}
        self._reports: list[dict] = []           # all reports (dict with date, period, ...)
        self._worker: _HistoryAIWorker | None = None
        self._current_date: str = ""
        self._current_period: str = "daily"
        self._initial_date = initial_date
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
            "QLineEdit{background:white;color:#333;border:none;border-radius:4px;padding:6px 10px;min-width:180px;}"
        )
        self.search_input.textChanged.connect(self._load_dates)
        hl.addWidget(self.search_input)
        self.period_filter = QComboBox()
        self.period_filter.addItems(["全部", "日报", "周报", "月报"])
        self.period_filter.setStyleSheet(
            "QComboBox{background:white;color:#333;border:none;border-radius:4px;padding:4px 8px;}"
            "QComboBox::drop-down{border:none;}"
        )
        self.period_filter.currentIndexChanged.connect(self._load_dates)
        hl.addWidget(self.period_filter)
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

        self.ai_summary_btn = QPushButton("🤖 AI 总结")
        self.ai_summary_btn.setStyleSheet(
            "QPushButton{border:1px solid #ddd;border-radius:4px;padding:4px 12px;color:#ef5350;}"
            "QPushButton:hover{background:#ffebee;}"
            "QPushButton:disabled{color:#ccc;}"
        )
        self.ai_summary_btn.setToolTip("对当前选中日期的番茄钟记录生成 AI 总结")
        self.ai_summary_btn.clicked.connect(self._on_ai_summary)
        self.ai_summary_btn.setEnabled(False)
        top_bar.addWidget(self.ai_summary_btn)

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

        # Progress bar for AI summary
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(4)
        self.progress.setStyleSheet(
            "QProgressBar { border:none; background:#eee; border-radius:2px; }"
            "QProgressBar::chunk { background:#ef5350; border-radius:2px; }"
        )
        self.progress.hide()
        rl.addWidget(self.progress)

        splitter.addWidget(right)

        splitter.setSizes([200, 560])
        layout.addWidget(splitter, 1)

    PERIOD_LABELS = {"daily": "日报", "weekly": "周报", "monthly": "月报"}
    PERIOD_EMOJIS = {"daily": "📅", "weekly": "📊", "monthly": "📈"}

    def _load_dates(self):
        self.date_list.clear()
        self._reports = []

        keyword = self.search_input.text().strip().lower()
        period_filter = self.period_filter.currentText()
        # Map filter text to period value
        filter_period: str | None = None
        if period_filter == "日报":
            filter_period = "daily"
        elif period_filter == "周报":
            filter_period = "weekly"
        elif period_filter == "月报":
            filter_period = "monthly"

        # Collect reports (with period info)
        all_reports = self.db.get_all_reports()
        if filter_period:
            all_reports = [r for r in all_reports if r["period"] == filter_period]

        if keyword:
            all_reports = [
                r for r in all_reports
                if keyword in r["date"].lower()
                or keyword in (r.get("final_report") or "").lower()
                or keyword in (r.get("ai_summary") or "").lower()
            ]

        self._reports = all_reports

        # Also get dates with entries but no report
        report_dates = {r["date"] for r in all_reports}
        entry_dates = set(self.db.get_all_entry_dates())
        if keyword:
            entry_dates = {d for d in entry_dates if keyword in d.lower()}
        # Only show entry-only dates when no period filter (or filter is daily, since entries are daily)
        if filter_period is None or filter_period == "daily":
            entry_only_dates = sorted(entry_dates - report_dates, reverse=True)
        else:
            entry_only_dates = []

        if not all_reports and not entry_only_dates:
            item = QListWidgetItem("（暂无记录）")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.date_list.addItem(item)
            self.preview_title.setText("请选择左侧日期查看日报")
            self.preview.setPlainText("")
            return

        # Show reports first (with period badges), then entry-only dates
        for r in all_reports:
            emoji = self.PERIOD_EMOJIS.get(r["period"], "📄")
            label = r["period"]
            period_label = self.PERIOD_LABELS.get(r.get("period", "daily"), "日报")
            display = f"{emoji}  {r['date']}  · {period_label}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, (r["date"], r["period"]))
            self.date_list.addItem(item)

        for d in entry_only_dates:
            item = QListWidgetItem(f"⚠ {d}")
            item.setForeground(QColor("gray"))
            item.setData(Qt.ItemDataRole.UserRole, (d, None))
            self.date_list.addItem(item)

        # Pre-select initial date
        found = False
        if self._initial_date:
            for i in range(self.date_list.count()):
                data = self.date_list.item(i).data(Qt.ItemDataRole.UserRole)
                if data and data[0] == self._initial_date:
                    self.date_list.setCurrentRow(i)
                    found = True
                    break
            self._initial_date = None
        if not found:
            self.date_list.setCurrentRow(0)

    def _on_date_selected(self, current: QListWidgetItem, _prev):
        if current is None:
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        date_str, period = data
        self._current_date = date_str
        self._current_period = period or "daily"

        # Try to get the report (with period if we have one)
        has_report = period is not None
        report = None
        if has_report:
            # Find matching report in loaded reports
            for r in self._reports:
                if r["date"] == date_str and r["period"] == period:
                    report = r
                    break

        # Check for pomodoro entries
        entries = self.db.get_entries_by_date(date_str)
        valid_entries = [e for e in entries if not e.get("skipped") and e.get("content")]
        has_entries = len(valid_entries) > 0

        # AI button state
        can_ai = self.ai_client is not None and has_entries
        self.ai_summary_btn.setEnabled(can_ai)
        period_label = self.PERIOD_LABELS.get(period or "daily", "日报")
        if has_report:
            self.ai_summary_btn.setText("🤖 AI 总结")
        else:
            self.ai_summary_btn.setText("🤖 生成日报")

        if has_report and report:
            self.preview_title.setText(f"📄  {date_str} · {period_label}")
            content = report.get("final_report") or report.get("ai_summary") or ""
            if not content:
                lines = [f"- {e.get('start_time','')[:5]}-{e.get('end_time','')[:5]}  {e.get('content','')}"
                         for e in (report.get("raw_entries") or [])
                         if not e.get("skipped")]
                content = "\n".join(lines) or "（无内容）"
            self.preview.setPlainText(content)
        elif has_entries:
            self.preview_title.setText(f"📋  {date_str} · 未生成日报")
            lines = [f"## {date_str} 番茄钟记录", ""]
            completed = [e for e in entries if not e.get("skipped")]
            lines.append(f"共 {len(completed)} 个番茄钟，约 {len(completed) * 25} 分钟专注工作。")
            lines.append("")
            for e in entries:
                if e.get("skipped"):
                    lines.append(f"- {e['start_time'][:5]}-{e['end_time'][:5]}  （已跳过）")
                else:
                    tags = ", ".join(e.get("tags") or [])
                    tag_str = f"[{tags}] " if tags else ""
                    lines.append(f"- {e['start_time'][:5]}-{e['end_time'][:5]}  {tag_str}{e.get('content','（未记录）')}")
            lines.append("")
            lines.append("---")
            lines.append("💡 该日期尚未生成日报，点击 **🤖 生成日报** 按钮即可生成。")
            self.preview.setPlainText("\n".join(lines))
        else:
            self.preview_title.setText(f"📋  {date_str} · 无记录")
            self.preview.setPlainText("该日期没有有效番茄钟记录。")

    def _copy_current(self):
        text = self.preview.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    # ------------------------------------------------------------------
    # AI 总结
    # ------------------------------------------------------------------

    def _on_ai_summary(self):
        if not self.ai_client or not self._current_date:
            return

        # Get entries for the selected date
        entries = self.db.get_entries_by_date(self._current_date)
        valid = [e for e in entries if not e.get("skipped") and e.get("content")]
        if not valid:
            QMessageBox.information(
                self,
                "POMATO",
                f"{self._current_date} 暂无有效番茄钟记录，无法生成 AI 总结。",
            )
            return

        # Disable button during generation
        self.ai_summary_btn.setEnabled(False)
        self.ai_summary_btn.setText("⏳ 生成中…")
        self.progress.show()
        self.preview.clear()

        self._worker = _HistoryAIWorker(self.ai_client, valid, self._current_date,
                                        todos=self.db.get_todos(date_str=self._current_date, include_done=True))
        self._worker.chunk_received.connect(self._on_ai_chunk)
        self._worker.finished.connect(self._on_ai_finished)
        self._worker.error.connect(self._on_ai_error)
        self._worker.start()

    def _on_ai_chunk(self, chunk: str):
        cursor = self.preview.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.preview.setTextCursor(cursor)
        self.preview.ensureCursorVisible()

    def _on_ai_finished(self, result: str):
        self.progress.hide()
        self.ai_summary_btn.setText("🤖 AI 总结")
        self.ai_summary_btn.setEnabled(True)
        self.preview_title.setText(f"📄  {self._current_date} · 日报 · AI 总结")
        # Save the AI summary to the database (history AI always generates daily)
        self.db.save_report(self._current_date,
                            self.db.get_entries_by_date(self._current_date),
                            period="daily", ai_summary=result, final_report=result)
        # Refresh: 新生成的日报会去掉 ⚠ 标记
        self._load_dates()
        # 重新选中当前日期
        for i in range(self.date_list.count()):
            data = self.date_list.item(i).data(Qt.ItemDataRole.UserRole)
            if data and data[0] == self._current_date:
                self.date_list.setCurrentRow(i)
                break

    def _on_ai_error(self, error_msg: str):
        logger.error("AI summary failed for %s: %s", self._current_date, error_msg)
        self.progress.hide()
        self.ai_summary_btn.setText("🤖 AI 总结")
        self.ai_summary_btn.setEnabled(True)
        QMessageBox.warning(
            self,
            "AI 总结失败",
            f"生成失败：{error_msg}\n\n请检查 API 配置或网络连接。",
        )
