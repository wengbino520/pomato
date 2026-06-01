from datetime import date

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class EntryItem(QFrame):
    """Single pomodoro entry row in the kanban list."""

    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            """
            QFrame {
                background: white;
                border: 1px solid #eee;
                border-radius: 6px;
                margin: 1px 0;
            }
            QFrame:hover { border-color: #ef5350; }
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Session badge
        badge = QLabel(f"#{entry['session_no']}")
        badge.setStyleSheet(
            "background:#ffebee; color:#ef5350; border-radius:10px;"
            "padding:2px 8px; font-size:11px; font-weight:bold;"
        )
        badge.setFixedWidth(38)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Time range
        start = entry["start_time"][:5]
        end = entry["end_time"][:5]
        time_lbl = QLabel(f"{start}-{end}")
        time_lbl.setStyleSheet("color:#999; font-size:11px;")
        time_lbl.setFixedWidth(94)

        # Content
        if entry.get("skipped"):
            text, style = "（已跳过）", "color:#ccc; font-size:13px;"
        else:
            text = entry.get("content") or ""
            style = "color:#333; font-size:13px;"
        content_lbl = QLabel(text)
        content_lbl.setStyleSheet(style)
        content_lbl.setWordWrap(True)
        content_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        # Tags
        tags_str = "  ".join(f"[{t}]" for t in entry.get("tags", []))
        tags_lbl = QLabel(tags_str)
        tags_lbl.setStyleSheet("color:#ef5350; font-size:11px;")

        layout.addWidget(badge)
        layout.addWidget(time_lbl)
        layout.addWidget(content_lbl)
        layout.addWidget(tags_lbl)


class MainWindow(QMainWindow):
    def __init__(self, config, db, timer, on_generate_report=None):
        super().__init__()
        self.config = config
        self.db = db
        self.timer = timer
        self.on_generate_report = on_generate_report
        self._setup_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        self.setWindowTitle("POMATO 番茄日志")
        self.setMinimumSize(560, 500)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── top header bar ─────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet("background:#ef5350;")
        header.setFixedHeight(56)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 8, 16, 8)

        title = QLabel("🍅 POMATO")
        title.setStyleSheet("color:white; font-size:18px; font-weight:bold;")

        self.date_label = QLabel()
        self.date_label.setStyleSheet("color:rgba(255,255,255,0.85); font-size:13px;")

        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(self.date_label)
        root.addWidget(header)

        # ── stats bar ──────────────────────────────────────────────────
        stats = QWidget()
        stats.setStyleSheet(
            "background:#fff3e0; border-bottom:1px solid #ffe0b2;"
        )
        stats.setFixedHeight(44)
        sl = QHBoxLayout(stats)
        sl.setContentsMargins(16, 0, 16, 0)

        self.pomodoro_count = QLabel("🍅 0 个番茄钟")
        self.pomodoro_count.setStyleSheet("font-size:13px; color:#e65100;")

        self.timer_status = QLabel("⏱ 等待中")
        self.timer_status.setStyleSheet("font-size:13px; color:#666;")

        sl.addWidget(self.pomodoro_count)
        sl.addStretch()
        sl.addWidget(self.timer_status)
        root.addWidget(stats)

        # ── entry list ─────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:#f8f8f8; }")

        self.entries_container = QWidget()
        self.entries_container.setStyleSheet("background:#f8f8f8;")
        self.entries_layout = QVBoxLayout(self.entries_container)
        self.entries_layout.setContentsMargins(12, 12, 12, 12)
        self.entries_layout.setSpacing(4)
        self.entries_layout.addStretch()

        scroll.setWidget(self.entries_container)
        root.addWidget(scroll, 1)

        # ── bottom action bar ──────────────────────────────────────────
        bottom = QWidget()
        bottom.setStyleSheet("background:white; border-top:1px solid #eee;")
        bottom.setFixedHeight(56)
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(16, 8, 16, 8)

        start_btn = QPushButton("▶  手动开始")
        start_btn.setStyleSheet(self._btn_style("#757575"))
        start_btn.clicked.connect(self.timer.manual_start)

        report_btn = QPushButton("📋  生成日报")
        report_btn.setStyleSheet(self._btn_style("#ef5350"))
        report_btn.clicked.connect(self._on_generate_report)

        bl.addWidget(start_btn)
        bl.addStretch()
        bl.addWidget(report_btn)
        root.addWidget(bottom)

        # Connect timer tick
        self.timer.tick.connect(self._on_timer_tick)

    @staticmethod
    def _btn_style(color: str) -> str:
        return (
            f"QPushButton {{ background:{color}; color:white; border:none;"
            "  border-radius:5px; padding:8px 20px; font-size:13px; }"
            "QPushButton:hover { opacity:0.9; }"
        )

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self):
        today = date.today().isoformat()
        self.date_label.setText(today)

        entries = self.db.get_entries_by_date(today)
        completed = sum(1 for e in entries if not e.get("skipped"))
        self.pomodoro_count.setText(f"🍅 {completed} 个番茄钟")

        # Clear old entry widgets (preserve the trailing stretch item)
        while self.entries_layout.count() > 1:
            item = self.entries_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not entries:
            empty = QLabel("今日暂无记录，开始你的第一个番茄钟吧 🍅")
            empty.setStyleSheet("color:#bbb; font-size:13px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.entries_layout.insertWidget(0, empty)
        else:
            for i, entry in enumerate(entries):
                self.entries_layout.insertWidget(i, EntryItem(entry))

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @pyqtSlot(int, str)
    def _on_timer_tick(self, remaining: int, label: str):
        if remaining < 0:
            self.timer_status.setText("⏱ 等待工作时间")
        else:
            mins, secs = divmod(remaining, 60)
            self.timer_status.setText(f"⏱ {label}  {mins:02d}:{secs:02d}")

    def _on_generate_report(self):
        if self.on_generate_report:
            self.on_generate_report()

    def closeEvent(self, event):
        # Hide to tray instead of quitting
        event.ignore()
        self.hide()
