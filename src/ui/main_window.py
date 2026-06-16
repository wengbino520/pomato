from datetime import date

from PyQt6.QtCore import QDate, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QCloseEvent, QFontMetrics, QResizeEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDateEdit,
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
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.services.logger import get_logger
from src.ui.styles import COLORS, STYLES, btn_style
from src.ui.history_window import HistoryWindow
from src.ui.todo_list_widget import TodoListWidget
from src.ui.reminder_list_widget import ReminderListWidget
from src.ui.stats_widget import StatsWidget
from src.ui.tag_selector_widget import TagSelectorWidget

logger = get_logger(__name__)


class EditEntryDialog(QDialog):
    """编辑条目：可修改时间段、内容、标签与关联待办 (F7-07)。"""

    def __init__(self, entry: dict, avail_tags: list[str], parent=None, reminder_engine=None):
        super().__init__(parent)
        self._reminder_engine = reminder_engine
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
        layout.addWidget(QLabel("标签（可多选）："))
        self._tag_selector = TagSelectorWidget(
            avail_tags, selected=entry.get("tags") or [], parent=self
        )
        layout.addWidget(self._tag_selector)

        # ---- 关联待办 (CD-01: extracted TodoLinkWidget) ----
        from src.ui.todo_link_widget import TodoLinkWidget
        current_todo_id = entry.get("todo_id")
        self._todo_link = TodoLinkWidget(
            self._reminder_engine, current_todo_id=current_todo_id, parent=self
        )
        layout.addWidget(self._todo_link)

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
        tags = self._tag_selector.selected_tags()
        return start, end, content, tags

    def get_todo_info(self) -> tuple[int, bool]:
        """返回 (todo_id, 是否标记完成)。0 表示未关联。(F7-07)"""
        return self._todo_link.get_todo_info()


class AddEntryDialog(QDialog):
    """手动补录条目：可填写时间段、内容、标签，关联待办。"""

    def __init__(self, tags: list[str], parent=None, reminder_engine=None):
        super().__init__(parent)
        self._reminder_engine = reminder_engine
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

        layout.addWidget(QLabel("标签（可多选）："))
        self._tag_selector = TagSelectorWidget(tags, parent=self)
        layout.addWidget(self._tag_selector)

        # ---- 关联待办 (CD-01: extracted TodoLinkWidget) ----
        from src.ui.todo_link_widget import TodoLinkWidget
        self._todo_link = TodoLinkWidget(self._reminder_engine, parent=self)
        layout.addWidget(self._todo_link)

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
        tags = self._tag_selector.selected_tags()
        return start, end, content, tags

    def get_todo_info(self) -> tuple[int, bool]:
        """返回 (todo_id, 是否标记完成)。0 表示未关联。"""
        return self._todo_link.get_todo_info()


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

        # Content (collapsible: single-line elided by default, expand via ▼/▲)
        skipped = entry.get("skipped")
        if skipped:
            text, style = "（已跳过）", "color:#ccc; font-size:13px;"
        else:
            text = entry.get("content") or ""
            style = "color:#333; font-size:13px;"
        self._full_text = text
        self._skipped = skipped

        content_lbl = QLabel(text)
        content_lbl.setStyleSheet(style)
        content_lbl.setWordWrap(True)
        content_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        # Single-line height based on font metrics (not sizeHint which reads full text)
        fm = QFontMetrics(content_lbl.font())
        content_lbl.setMaximumHeight(fm.height() + 2)
        self._content_lbl = content_lbl

        # Expand/collapse toggle (only for non-empty, non-skipped entries)
        self._expanded = False
        self._toggle_btn = QPushButton()
        self._toggle_btn.setFixedSize(18, 18)
        self._toggle_btn.setStyleSheet(
            "QPushButton{border:none;color:#bbb;font-size:9px;"
            "background:transparent;padding:0;}"
            "QPushButton:hover{color:#ef5350;}"
        )
        self._toggle_btn.clicked.connect(self._toggle_expand)
        self._update_toggle_visibility()

        # Tags
        tags_str = "  ".join(f"[{t}]" for t in entry.get("tags", []))
        tags_lbl = QLabel(tags_str)
        tags_lbl.setStyleSheet("color:#ef5350; font-size:11px;")

        # Associated todo (F7-07: bidirectional linking)
        todo_title = entry.get("todo_title")
        if todo_title:
            todo_lbl = QLabel(f"📋 {todo_title}")
            todo_lbl.setStyleSheet(
                "color:#5d4037; font-size:11px; background:#efebe9;"
                "border-radius:3px; padding:1px 6px;"
            )
            todo_lbl.setToolTip(f"关联待办: {todo_title}")

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
        layout.addWidget(self._content_lbl)
        layout.addWidget(self._toggle_btn)
        layout.addWidget(tags_lbl)
        if todo_title:
            layout.addWidget(todo_lbl)
        layout.addWidget(edit_btn)
        layout.addWidget(del_btn)

    def _update_toggle_visibility(self):
        """Show toggle only when content has meaningful text."""
        text = (self.entry.get("content") or "").strip()
        show = bool(text) and not self.entry.get("skipped")
        self._toggle_btn.setVisible(show)
        if show:
            self._expanded = False
            self._toggle_btn.setText("▼")
            self._toggle_btn.setToolTip("展开查看全文")

    def resizeEvent(self, event: QResizeEvent):
        """Recalculate elided text when widget resizes."""
        super().resizeEvent(event)
        if not self._expanded and not self._skipped:
            self._apply_elide()

    def _apply_elide(self):
        """Apply QFontMetrics.elidedText() to truncate with … in single line."""
        if not self._full_text:
            return
        fm = QFontMetrics(self._content_lbl.font())
        avail = self._content_lbl.width()
        if avail <= 0:
            return
        elided = fm.elidedText(self._full_text, Qt.TextElideMode.ElideRight, avail)
        self._content_lbl.setText(elided)

    def _toggle_expand(self):
        """Expand/collapse the content label between single-line and full text."""
        self._expanded = not self._expanded
        if self._expanded:
            self._content_lbl.setMaximumHeight(16777215)  # unconstrained
            self._content_lbl.setText(self._full_text)
            self._toggle_btn.setText("▲")
            self._toggle_btn.setToolTip("收起")
        else:
            fm = QFontMetrics(self._content_lbl.font())
            self._content_lbl.setMaximumHeight(fm.height() + 2)
            self._apply_elide()
            self._toggle_btn.setText("▼")
            self._toggle_btn.setToolTip("展开查看全文")


class MainWindow(QMainWindow):
    def __init__(self, config, db, timer, on_generate_report=None,
                 on_generate_weekly_report=None, on_generate_monthly_report=None,
                 on_open_settings=None):
        super().__init__()
        self.config = config
        self.db = db
        self.timer = timer
        self.on_generate_report = on_generate_report
        self.on_generate_weekly_report = on_generate_weekly_report
        self.on_generate_monthly_report = on_generate_monthly_report
        self.on_open_settings = on_open_settings
        self.view_date = date.today()
        self._setup_ui()
        self.refresh()
        # 监听计时器状态变化以同步暂停按钮文字
        self.timer.state_changed.connect(self._on_timer_state_changed)

    # ------------------------------------------------------------------
    # UI construction (CD-02: split into 4 builder methods)
    # ------------------------------------------------------------------

    def _setup_ui(self):
        self.setWindowTitle("POMATO 番茄日志")
        self.setMinimumSize(600, 460)
        self.resize(1200, 742)
        qr = self.frameGeometry()
        cp = self.screen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_stats_bar())
        root.addWidget(self._build_tabs(), 1)
        root.addWidget(self._build_bottom_bar())

        self.timer.tick.connect(self._on_timer_tick)

    def _build_header(self) -> QWidget:
        """顶部栏：标题 + 日期导航 + 日历 (CD-02)。"""
        header = QWidget()
        header.setStyleSheet(STYLES["header_bar"])
        header.setFixedHeight(56)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 8, 16, 8)

        title = QLabel("🍅 POMATO")
        title.setStyleSheet("color:white; font-size:18px; font-weight:bold;")

        prev_day_btn = QPushButton("◀")
        prev_day_btn.setFixedSize(30, 30)
        prev_day_btn.setStyleSheet(STYLES["arrow_btn"])
        prev_day_btn.clicked.connect(self._prev_day)

        next_day_btn = QPushButton("▶")
        next_day_btn.setFixedSize(30, 30)
        next_day_btn.setStyleSheet(STYLES["arrow_btn"])
        next_day_btn.clicked.connect(self._next_day)

        self.view_date_edit = QDateEdit()
        self.view_date_edit.setCalendarPopup(True)
        self.view_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.view_date_edit.setDate(QDate.currentDate())
        self.view_date_edit.setFixedWidth(148)
        self.view_date_edit.setStyleSheet(
            "QDateEdit { background:white; color:#333; border:none; border-radius:4px;"
            "  padding:4px 10px; padding-right:24px; }"
        )
        self.view_date_edit.dateChanged.connect(self._on_view_date_changed)
        calendar = self.view_date_edit.calendarWidget()
        if calendar is not None:
            calendar.setMinimumSize(420, 320)
            calendar.setGridVisible(True)
            calendar.setStyleSheet(
                f"QCalendarWidget QWidget {{ background:{COLORS['primary']}; }}"
                f"QCalendarWidget QToolButton {{ color:white; background:{COLORS['primary']};"
                f"  border:none; min-height:28px; min-width:28px; }}"
                f"QCalendarWidget QToolButton:hover {{ background:{COLORS['primary_dark']}; }}"
                "QCalendarWidget QAbstractSpinBox { min-width: 92px; padding: 2px 6px; }"
                "QCalendarWidget QSpinBox { min-width: 92px; }"
                "QCalendarWidget QMenu { background:white; }"
            )

        today_btn = QPushButton("今天")
        today_btn.setStyleSheet(STYLES["btn_grey"])
        today_btn.clicked.connect(self._jump_to_today)

        self.date_label = QLabel()
        self.date_label.setStyleSheet(
            f"color:{COLORS['white_translucent']}; font-size:13px;"
        )

        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(prev_day_btn)
        hl.addWidget(self.view_date_edit)
        hl.addWidget(next_day_btn)
        hl.addWidget(today_btn)
        hl.addWidget(self.date_label)
        return header

    def _build_stats_bar(self) -> QWidget:
        """统计栏：番茄计数 + 专注时长 + 计时器状态 (CD-02)。"""
        stats = QWidget()
        stats.setStyleSheet(STYLES["stats_bar"])
        stats.setFixedHeight(44)
        sl = QHBoxLayout(stats)
        sl.setContentsMargins(16, 0, 16, 0)

        self.pomodoro_count = QLabel("🍅 0 个番茄钟")
        self.pomodoro_count.setStyleSheet(f"font-size:13px; color:{COLORS['orange']};")
        self.focus_time = QLabel("⏱ 专注 0 分钟")
        self.focus_time.setStyleSheet(f"font-size:13px; color:{COLORS['orange']};")
        self.timer_status = QLabel("⏱ 等待中")
        self.timer_status.setStyleSheet(f"font-size:13px; color:{COLORS['grey_medium']};")

        sl.addWidget(self.pomodoro_count)
        sl.addWidget(self.focus_time)
        sl.addStretch()
        sl.addWidget(self.timer_status)
        return stats

    def _build_tabs(self) -> QTabWidget:
        """Tab 面板：番茄记录 / 待办 / 提醒 (CD-02)。"""
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(STYLES["tab_widget"])

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(STYLES["scroll_area"])
        self.entries_container = QWidget()
        self.entries_container.setStyleSheet(f"background:{COLORS['page_bg']};")
        self.entries_layout = QVBoxLayout(self.entries_container)
        self.entries_layout.setContentsMargins(12, 12, 12, 12)
        self.entries_layout.setSpacing(4)
        self.entries_layout.addStretch()
        scroll.setWidget(self.entries_container)
        self.tab_widget.addTab(scroll, "🍅 番茄")

        self._todo_tab = QWidget()
        self._todo_tab_layout = QVBoxLayout(self._todo_tab)
        self._todo_tab_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_widget.addTab(self._todo_tab, "📋 待办")

        self._reminder_tab = QWidget()
        self._reminder_tab_layout = QVBoxLayout(self._reminder_tab)
        self._reminder_tab_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_widget.addTab(self._reminder_tab, "⏰ 提醒")

        self._stats_widget = StatsWidget(self.db)
        self.tab_widget.addTab(self._stats_widget, "📊 统计")

        return self.tab_widget

    def _build_bottom_bar(self) -> QWidget:
        """底部操作栏：手动开始 / 补录 / 暂停 / 历史 / 日报 / 设置 (CD-02)。"""
        bottom = QWidget()
        bottom.setStyleSheet(STYLES["bottom_bar"])
        bottom.setFixedHeight(56)
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(16, 8, 16, 8)

        start_btn = QPushButton("▶  手动开始")
        start_btn.setStyleSheet(STYLES["btn_grey"])
        start_btn.clicked.connect(self.timer.manual_start)

        add_btn = QPushButton("＋  手动补录")
        add_btn.setStyleSheet(STYLES["btn_brown"])
        add_btn.clicked.connect(self._on_add_entry)

        self.pause_btn = QPushButton("⏸  暂停")
        self.pause_btn.setStyleSheet(STYLES["btn_blue"])
        self.pause_btn.clicked.connect(self._on_pause_resume)
        self.pause_btn.setEnabled(False)

        self.history_btn = QPushButton("📚  历史报告")
        self.history_btn.setStyleSheet(STYLES["btn_history"])
        self.history_btn.clicked.connect(self._open_history_window)

        report_btn = QPushButton("📋  日报")
        report_btn.setStyleSheet(STYLES["btn_primary"])
        report_btn.clicked.connect(self._on_generate_report)

        weekly_btn = QPushButton("📋  周报")
        weekly_btn.setStyleSheet(STYLES["btn_primary"])
        weekly_btn.clicked.connect(self._on_generate_weekly_report)

        monthly_btn = QPushButton("📋  月报")
        monthly_btn.setStyleSheet(STYLES["btn_primary"])
        monthly_btn.clicked.connect(self._on_generate_monthly_report)

        settings_btn = QPushButton("⚙  设置")
        settings_btn.setStyleSheet(STYLES["btn_primary"])
        settings_btn.clicked.connect(self._on_open_settings)

        bl.addWidget(start_btn)
        bl.addWidget(add_btn)
        bl.addWidget(self.pause_btn)
        bl.addStretch()
        bl.addWidget(self.history_btn)
        bl.addWidget(report_btn)
        bl.addWidget(weekly_btn)
        bl.addWidget(monthly_btn)
        bl.addWidget(settings_btn)
        return bottom

    @staticmethod
    def _btn_style(color: str) -> str:
        return btn_style(color)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self):
        selected_date = self.view_date
        today = date.today()
        date_str = selected_date.isoformat()
        status = "今日" if selected_date == today else "历史"
        self.date_label.setText(f"{date_str} · {status}")

        entries = self.db.get_entries_by_date(date_str)
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
            empty = QLabel(f"{date_str} 暂无记录，开始你的第一个番茄钟吧 🍅")
            empty.setStyleSheet("color:#bbb; font-size:13px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.entries_layout.insertWidget(0, empty)
        else:
            for i, entry in enumerate(entries):
                # 按时间排序后重新编号，确保显示序号连贯统一
                entry["session_no"] = i + 1
                item = EntryItem(entry)
                item.edit_requested.connect(self._on_edit_entry)
                item.delete_requested.connect(self._on_delete_entry)
                self.entries_layout.insertWidget(i, item)

        # Also refresh todo/reminder widgets if available (F7-07 fix)
        if hasattr(self, '_todo_widget'):
            self._todo_widget.refresh(date_str=date_str)
        if hasattr(self, '_reminder_widget'):
            self._reminder_widget.refresh()

        # 刷新统计 Tab (C3)
        self._stats_widget.refresh(date_str)

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

    def _on_view_date_changed(self, qdate: QDate):
        self.view_date = qdate.toPyDate()
        self.refresh()

    def _jump_to_today(self):
        self.view_date_edit.setDate(QDate.currentDate())

    def _prev_day(self):
        self.view_date_edit.setDate(self.view_date_edit.date().addDays(-1))

    def _next_day(self):
        self.view_date_edit.setDate(self.view_date_edit.date().addDays(1))

    def _open_history_window(self):
        from src.services.ai_client import AIClient
        HistoryWindow(
            self.db, self,
            ai_client=AIClient(self.config),
            config=self.config,
            initial_date=self.view_date.isoformat(),
        ).exec()

    def _on_generate_report(self):
        if self.on_generate_report:
            self.on_generate_report(self.view_date.isoformat())

    def _on_generate_weekly_report(self):
        if self.on_generate_weekly_report:
            self.on_generate_weekly_report(self.view_date.isoformat())

    def _on_generate_monthly_report(self):
        if self.on_generate_monthly_report:
            self.on_generate_monthly_report(self.view_date.isoformat())

    def _on_pause_resume(self):
        self.timer.pause_resume()
        if self.timer._paused:
            self.pause_btn.setText("▶  继续")
            self.pause_btn.setStyleSheet(self._btn_style("#66bb6a"))
        else:
            self.pause_btn.setText("⏸  暂停")
            self.pause_btn.setStyleSheet(self._btn_style("#1976d2"))

    def _on_open_settings(self):
        if self.on_open_settings:
            self.on_open_settings()

    @pyqtSlot(str)
    def _on_timer_state_changed(self, state: str):
        if state == "work":
            self.pause_btn.setEnabled(True)
            self.pause_btn.setText("⏸  暂停")
            self.pause_btn.setStyleSheet(self._btn_style("#1976d2"))
        elif state in ("short_break", "long_break"):
            self.pause_btn.setEnabled(False)
        else:
            self.pause_btn.setEnabled(False)

    def _on_edit_entry(self, entry: dict):
        avail_tags = self.config.get("custom_tags", [])
        engine = getattr(self, '_reminder_engine', None)
        dlg = EditEntryDialog(entry, avail_tags, self, reminder_engine=engine)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            start, end, content, tags = dlg.get_values()
            todo_id, mark_done = dlg.get_todo_info()
            # F7-07: pass todo_id to update_entry
            self.db.update_entry(entry["id"], content, tags, start, end,
                                 todo_id=todo_id if todo_id else None)
            logger.info("Entry edited: id=%d, tags=%s", entry["id"], tags)
            # Update todo linkage if changed
            if engine:
                old_todo_id = entry.get("todo_id")
                if todo_id and todo_id != old_todo_id:
                    if mark_done:
                        engine.update_todo(todo_id, pomodoro_id=entry["id"], status="done")
                    else:
                        engine.update_todo(todo_id, pomodoro_id=entry["id"])
                elif todo_id and todo_id == old_todo_id and mark_done:
                    engine.update_todo(todo_id, pomodoro_id=entry["id"], status="done")
                elif not todo_id and old_todo_id:
                    engine.update_todo(old_todo_id, pomodoro_id=None)
            self.refresh()

    def _on_delete_entry(self, entry_id: int):
        logger.info("Entry deleted: id=%d", entry_id)
        self.db.delete_entry(entry_id)
        self.refresh()

    def _on_add_entry(self):
        tags = self.config.get("custom_tags", [])
        target_date = self.view_date.isoformat()
        added = 0
        while True:
            dlg = AddEntryDialog(tags, self, reminder_engine=getattr(self, '_reminder_engine', None))
            if dlg.exec() != QDialog.DialogCode.Accepted:
                break
            start, end, content, selected_tags = dlg.get_values()
            todo_id, mark_done = dlg.get_todo_info()
            session_no = self.db.get_next_session_no(target_date)
            # F7-07: pass todo_id to add_entry for bidirectional linking
            entry_id = self.db.add_entry(target_date, session_no, start, end, content,
                                         selected_tags, skipped=False,
                                         todo_id=todo_id if todo_id else None)
            if todo_id and entry_id:
                engine = getattr(self, '_reminder_engine', None)
                if engine:
                    if mark_done:
                        engine.update_todo(todo_id, pomodoro_id=entry_id, status="done")
                    else:
                        engine.update_todo(todo_id, pomodoro_id=entry_id)
            added += 1
        if added:
            logger.info("Manual entry added: %d entries for %s", added, target_date)
            self.refresh()

    # ------------------------------------------------------------------
    # Phase B: Tab 切换 + 待办/提醒嵌入
    # ------------------------------------------------------------------

    def set_reminder_engine(self, engine):
        """注入 ReminderEngine，初始化待办/提醒 Tab（由 TrayManager 调用）。"""
        self._reminder_engine = engine

        self._todo_widget = TodoListWidget(engine)
        self._todo_tab_layout.addWidget(self._todo_widget)
        self._todo_widget.refresh()

        self._reminder_widget = ReminderListWidget(engine)
        self._reminder_tab_layout.addWidget(self._reminder_widget)

    def switch_to_todo_tab(self):
        self.show()
        self.raise_()
        self.tab_widget.setCurrentIndex(1)

    def switch_to_reminder_tab(self):
        self.show()
        self.raise_()
        self.tab_widget.setCurrentIndex(2)

    def switch_to_pomodoro_tab(self):
        self.tab_widget.setCurrentIndex(0)

    def closeEvent(self, a0: QCloseEvent | None):
        # Hide to tray instead of quitting
        if a0 is not None:
            a0.ignore()
        self.hide()
