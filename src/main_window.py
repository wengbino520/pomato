from datetime import date

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class EditEntryDialog(QDialog):
    """编辑条目：可修改时间段、内容与标签。"""

    def __init__(self, entry: dict, avail_tags: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑记录")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)

        # ---- 时间行 ----
        def _parse_hm(t: str | None, default_h: int, default_m: int):
            if t:
                parts = t.split(":")
                try:
                    return int(parts[0]), int(parts[1])
                except (IndexError, ValueError):
                    pass
            return default_h, default_m

        sh, sm = _parse_hm(entry.get("start_time"), 9, 0)
        eh, em = _parse_hm(entry.get("end_time"), 9, 25)

        self.start_hour = QSpinBox(); self.start_hour.setRange(0, 23); self.start_hour.setValue(sh); self.start_hour.setSuffix(" 时"); self.start_hour.setFixedWidth(90)
        self.start_minute = QSpinBox(); self.start_minute.setRange(0, 59); self.start_minute.setValue(sm); self.start_minute.setSuffix(" 分"); self.start_minute.setFixedWidth(90)
        self.end_hour = QSpinBox(); self.end_hour.setRange(0, 23); self.end_hour.setValue(eh); self.end_hour.setSuffix(" 时"); self.end_hour.setFixedWidth(90)
        self.end_minute = QSpinBox(); self.end_minute.setRange(0, 59); self.end_minute.setValue(em); self.end_minute.setSuffix(" 分"); self.end_minute.setFixedWidth(90)

        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("开始："))
        time_row.addWidget(self.start_hour)
        time_row.addWidget(self.start_minute)
        time_row.addSpacing(12)
        time_row.addWidget(QLabel("结束："))
        time_row.addWidget(self.end_hour)
        time_row.addWidget(self.end_minute)
        time_row.addStretch()
        layout.addLayout(time_row)

        # ---- 内容 ----
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(entry.get("content") or "")
        self.text_edit.setMinimumHeight(80)
        layout.addWidget(QLabel("工作内容："))
        layout.addWidget(self.text_edit)

        # ---- 标签 ----
        self.tags_combo = QComboBox()
        self.tags_combo.setEditable(True)
        self.tags_combo.addItem("")
        for tag in avail_tags:
            self.tags_combo.addItem(tag)
        self.tags_combo.setCurrentText(", ".join(entry.get("tags") or []))
        self.tags_combo.setPlaceholderText("可输入多个标签，逗号分隔")
        layout.addWidget(QLabel("标签："))
        layout.addWidget(self.tags_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        start_total = self.start_hour.value() * 60 + self.start_minute.value()
        end_total = self.end_hour.value() * 60 + self.end_minute.value()
        if start_total >= end_total:
            QMessageBox.warning(self, "时间不合法", "结束时间必须晚于开始时间。")
            return
        self.accept()

    def get_values(self) -> tuple[str, str, str, list[str]]:
        start = f"{self.start_hour.value():02d}:{self.start_minute.value():02d}:00"
        end = f"{self.end_hour.value():02d}:{self.end_minute.value():02d}:00"
        content = self.text_edit.toPlainText().strip()
        tags = [t.strip() for t in self.tags_combo.currentText().split(",") if t.strip()]
        return start, end, content, tags


class AddEntryDialog(QDialog):
    """手动补录条目：可填写时间段、内容与标签。"""

    def __init__(self, tags: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("手动补录")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        self.start_hour = QSpinBox()
        self.start_hour.setRange(0, 23)
        self.start_hour.setValue(9)
        self.start_hour.setSuffix(" 时")
        self.start_hour.setFixedWidth(90)

        self.start_minute = QSpinBox()
        self.start_minute.setRange(0, 59)
        self.start_minute.setValue(0)
        self.start_minute.setSuffix(" 分")
        self.start_minute.setFixedWidth(90)

        self.end_hour = QSpinBox()
        self.end_hour.setRange(0, 23)
        self.end_hour.setValue(9)
        self.end_hour.setSuffix(" 时")
        self.end_hour.setFixedWidth(90)

        self.end_minute = QSpinBox()
        self.end_minute.setRange(0, 59)
        self.end_minute.setValue(25)
        self.end_minute.setSuffix(" 分")
        self.end_minute.setFixedWidth(90)

        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("开始："))
        time_row.addWidget(self.start_hour)
        time_row.addWidget(self.start_minute)
        time_row.addSpacing(12)
        time_row.addWidget(QLabel("结束："))
        time_row.addWidget(self.end_hour)
        time_row.addWidget(self.end_minute)
        time_row.addStretch()
        layout.addLayout(time_row)

        layout.addWidget(QLabel("工作内容："))
        self.content_edit = QTextEdit()
        self.content_edit.setMinimumHeight(90)
        layout.addWidget(self.content_edit)

        layout.addWidget(QLabel("标签："))
        self.tags_combo = QComboBox()
        self.tags_combo.setEditable(True)
        self.tags_combo.addItem("")
        for tag in tags:
            self.tags_combo.addItem(tag)
        self.tags_combo.setCurrentIndex(0)
        self.tags_combo.setPlaceholderText("可输入多个标签，逗号分隔")
        layout.addWidget(self.tags_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        start_total = self.start_hour.value() * 60 + self.start_minute.value()
        end_total = self.end_hour.value() * 60 + self.end_minute.value()
        if start_total >= end_total:
            QMessageBox.warning(self, "时间不合法", "结束时间必须晚于开始时间。")
            return
        content = self.content_edit.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "内容为空", "请填写工作内容。")
            return
        self.accept()

    def get_values(self) -> tuple[str, str, str, list[str]]:
        start = f"{self.start_hour.value():02d}:{self.start_minute.value():02d}:00"
        end = f"{self.end_hour.value():02d}:{self.end_minute.value():02d}:00"
        content = self.content_edit.toPlainText().strip()
        raw_tags = self.tags_combo.currentText().strip()
        tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        return start, end, content, tags


class EntryItem(QFrame):
    """Single pomodoro entry row in the kanban list."""

    edit_requested = pyqtSignal(dict)    # entry dict
    delete_requested = pyqtSignal(int)   # entry id

    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.entry = entry
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
        layout.setContentsMargins(12, 8, 8, 8)
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

        # Edit / Delete buttons (hidden until hover via enterEvent)
        edit_btn = QPushButton("✏")
        edit_btn.setFixedSize(26, 26)
        edit_btn.setToolTip("编辑")
        edit_btn.setStyleSheet(
            "QPushButton{border:none;color:#888;font-size:14px;background:transparent;}"
            "QPushButton:hover{color:#ef5350;}"
        )
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.entry))

        del_btn = QPushButton("🗑")
        del_btn.setFixedSize(26, 26)
        del_btn.setToolTip("删除")
        del_btn.setStyleSheet(
            "QPushButton{border:none;color:#888;font-size:14px;background:transparent;}"
            "QPushButton:hover{color:#ef5350;}"
        )
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.entry["id"]))

        layout.addWidget(badge)
        layout.addWidget(time_lbl)
        layout.addWidget(content_lbl)
        layout.addWidget(tags_lbl)
        layout.addWidget(edit_btn)
        layout.addWidget(del_btn)


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

        self.focus_time = QLabel("⏱ 专注 0 分钟")
        self.focus_time.setStyleSheet("font-size:13px; color:#e65100;")

        self.timer_status = QLabel("⏱ 等待中")
        self.timer_status.setStyleSheet("font-size:13px; color:#666;")

        sl.addWidget(self.pomodoro_count)
        sl.addWidget(self.focus_time)
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

        add_btn = QPushButton("＋  手动补录")
        add_btn.setStyleSheet(self._btn_style("#5d4037"))
        add_btn.clicked.connect(self._on_add_entry)

        report_btn = QPushButton("📋  生成日报")
        report_btn.setStyleSheet(self._btn_style("#ef5350"))
        report_btn.clicked.connect(self._on_generate_report)

        bl.addWidget(start_btn)
        bl.addWidget(add_btn)
        bl.addStretch()
        bl.addWidget(report_btn)
        root.addWidget(bottom)

        # Connect timer tick
        self.timer.tick.connect(self._on_timer_tick)

    @staticmethod
    def _btn_style(color: str) -> str:
        return (
            f"QPushButton {{ background:{color}; color:white; border:none;"
            f"  border-radius:5px; padding:8px 20px; font-size:13px; }}"
            f"QPushButton:hover {{ background:{color}; border:1px solid rgba(255,255,255,0.5); }}"
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
        focus_min = completed * self.config.get("pomodoro_duration", 25)
        self.focus_time.setText(f"⏳ 专注 {focus_min} 分钟")

        # Clear old entry widgets (preserve the trailing stretch item)
        while self.entries_layout.count() > 1:
            item = self.entries_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not entries:
            empty = QLabel("今日暂无记录，开始你的第一个番茄钟吧 🍅")
            empty.setStyleSheet("color:#bbb; font-size:13px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.entries_layout.insertWidget(0, empty)
        else:
            for i, entry in enumerate(entries):
                item = EntryItem(entry)
                item.edit_requested.connect(self._on_edit_entry)
                item.delete_requested.connect(self._on_delete_entry)
                self.entries_layout.insertWidget(i, item)

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

    def _on_edit_entry(self, entry: dict):
        avail_tags = self.config.get("custom_tags", [])
        dlg = EditEntryDialog(entry, avail_tags, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            start, end, content, tags = dlg.get_values()
            self.db.update_entry(entry["id"], content, tags, start, end)
            self.refresh()

    def _on_delete_entry(self, entry_id: int):
        self.db.delete_entry(entry_id)
        self.refresh()

    def _on_add_entry(self):
        tags = self.config.get("custom_tags", [])
        today = date.today().isoformat()
        added = 0
        while True:
            dlg = AddEntryDialog(tags, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                break
            start, end, content, selected_tags = dlg.get_values()
            session_no = self.db.get_next_session_no(today)
            self.db.add_entry(today, session_no, start, end, content, selected_tags, skipped=False)
            added += 1
        if added:
            self.refresh()

    def closeEvent(self, a0: QCloseEvent | None):
        # Hide to tray instead of quitting
        if a0 is not None:
            a0.ignore()
        self.hide()
