from datetime import date
import re

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class _AIWorker(QThread):
    chunk_received = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, ai_client, entries: list[dict], report_date: str):
        super().__init__()
        self.ai_client = ai_client
        self.entries = entries
        self.report_date = report_date

    def run(self):
        try:
            result = self.ai_client.generate_report(
                self.entries,
                self.report_date,
                on_chunk=lambda c: self.chunk_received.emit(c),
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class ReportWindow(QDialog):
    def __init__(self, config, db, ai_client, parent=None):
        super().__init__(parent)
        self.config = config
        self.db = db
        self.ai_client = ai_client
        self.report_date = date.today().isoformat()
        self.entries = db.get_entries_by_date(self.report_date)
        self._worker: _AIWorker | None = None
        self._setup_ui()
        self._start_generation()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self):
        self.setWindowTitle("POMATO · 工作日报")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(720, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # header
        hl = QHBoxLayout()
        title = QLabel(f"📋 工作日报 · {self.report_date}")
        title.setStyleSheet("font-size:15px; font-weight:bold; color:#333;")
        self.status_label = QLabel("AI 生成中…")
        self.status_label.setStyleSheet("color:#ef5350; font-size:12px;")
        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(self.status_label)
        layout.addLayout(hl)

        # editor
        self.editor = QTextEdit()
        self.editor.setFont(QFont("Consolas", 12))
        self.editor.setStyleSheet(
            "QTextEdit { border:1px solid #eee; border-radius:6px;"
            "  padding:12px; background:#fafafa; }"
        )
        layout.addWidget(self.editor, 1)

        # indeterminate progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(4)
        self.progress.setStyleSheet(
            "QProgressBar { border:none; background:#eee; border-radius:2px; }"
            "QProgressBar::chunk { background:#ef5350; border-radius:2px; }"
        )
        layout.addWidget(self.progress)

        # buttons
        bl = QHBoxLayout()

        self.regenerate_btn = QPushButton("🔄 重新生成")
        self.regenerate_btn.setEnabled(False)
        self.regenerate_btn.setStyleSheet(self._btn_style("#757575"))
        self.regenerate_btn.clicked.connect(self._start_generation)

        self.copy_btn = QPushButton("📋 复制")
        self.copy_btn.setEnabled(False)
        self.copy_btn.setStyleSheet(self._btn_style("#1976d2"))
        self.copy_btn.clicked.connect(self._copy_to_clipboard)

        self.export_btn = QPushButton("💾 导出 Markdown")
        self.export_btn.setEnabled(False)
        self.export_btn.setStyleSheet(self._btn_style("#388e3c"))
        self.export_btn.clicked.connect(self._export_markdown)

        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(self._btn_style("#9e9e9e"))
        close_btn.clicked.connect(self.accept)

        bl.addWidget(self.regenerate_btn)
        bl.addStretch()
        bl.addWidget(self.copy_btn)
        bl.addWidget(self.export_btn)
        bl.addWidget(close_btn)
        layout.addLayout(bl)

    @staticmethod
    def _btn_style(color: str) -> str:
        return (
            f"QPushButton {{ background:{color}; color:white; border:none;"
            f"  border-radius:5px; padding:8px 16px; font-size:13px; }}"
            "QPushButton:disabled { background:#ccc; }"
        )

    # ------------------------------------------------------------------
    # Generation flow
    # ------------------------------------------------------------------

    def _start_generation(self):
        self.editor.clear()
        self.progress.show()
        self.status_label.setText("AI 生成中…")
        self.status_label.setStyleSheet("color:#ef5350; font-size:12px;")
        self.regenerate_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.export_btn.setEnabled(False)

        self._worker = _AIWorker(self.ai_client, self.entries, self.report_date)
        self._worker.chunk_received.connect(self._on_chunk)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_chunk(self, chunk: str):
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.editor.setTextCursor(cursor)
        self.editor.ensureCursorVisible()

    def _on_finished(self, result: str):
        self.progress.hide()
        self.status_label.setText("✓ 生成完成，可直接编辑后导出")
        self.status_label.setStyleSheet("color:#388e3c; font-size:12px;")
        self.regenerate_btn.setEnabled(True)
        self.copy_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.db.save_report(self.report_date, self.entries, ai_summary=result, final_report=result)

    def _on_error(self, error_msg: str):
        self.progress.hide()
        self.status_label.setText("⚠ AI 生成失败，已展示原始记录")
        self.status_label.setStyleSheet("color:#f44336; font-size:12px;")
        self.regenerate_btn.setEnabled(True)
        fallback = self._generate_fallback()
        self.editor.setPlainText(fallback)
        self.copy_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        QMessageBox.warning(
            self,
            "AI 生成失败",
            f"原因：{error_msg}\n\n已展示原始记录，您可手动整理后导出。",
        )

    def _generate_fallback(self) -> str:
        valid = [e for e in self.entries if not e.get("skipped") and e.get("content")]
        lines = [f"# 工作日报 {self.report_date}", ""]
        lines.append(f"## 今日记录（共 {len(valid)} 个番茄钟）")
        for e in valid:
            tags = ", ".join(e.get("tags") or [])
            tag_str = f"[{tags}] " if tags else ""
            lines.append(f"- {e['start_time'][:5]}-{e['end_time'][:5]} {tag_str}{e['content']}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _copy_to_clipboard(self):
        QApplication.clipboard().setText(self.editor.toPlainText())
        original = self.copy_btn.text()
        self.copy_btn.setText("✓ 已复制")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.copy_btn.setText(original))

    def _export_markdown(self):
        default_name = f"日报_{self.report_date}.md"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出日报", default_name, "Markdown 文件 (*.md);;文本文件 (*.txt)"
        )
        if path:
            markdown = self.editor.toPlainText()
            text = markdown
            if path.lower().endswith(".txt"):
                text = self._markdown_to_plain_text(markdown)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self.db.save_report(self.report_date, self.entries, final_report=markdown)
            QMessageBox.information(self, "导出成功", f"日报已保存至：\n{path}")

    @staticmethod
    def _markdown_to_plain_text(markdown: str) -> str:
        lines = []
        for line in markdown.splitlines():
            stripped = line.strip()
            if not stripped:
                lines.append("")
                continue

            stripped = re.sub(r"^#{1,6}\s*", "", stripped)
            stripped = re.sub(r"^[-*+]\s+", "- ", stripped)
            stripped = re.sub(r"\*\*(.*?)\*\*", r"\1", stripped)
            stripped = re.sub(r"\*(.*?)\*", r"\1", stripped)
            stripped = re.sub(r"`(.*?)`", r"\1", stripped)
            lines.append(stripped)

        plain = "\n".join(lines)
        plain = re.sub(r"\n{3,}", "\n\n", plain)
        return plain.strip() + "\n"
