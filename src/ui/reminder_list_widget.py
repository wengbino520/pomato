"""
ReminderListWidget — 自包含提醒列表组件 (TASK-10)
"""
from PyQt6.QtCore import Qt, QTime, QDate
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QPushButton, QLabel, QFrame,
    QDialog, QDialogButtonBox, QLineEdit, QTimeEdit,
    QComboBox, QSpinBox, QDateEdit, QMessageBox,
)

from src.services.logger import get_logger

logger = get_logger(__name__)


class _ReminderEditDialog(QDialog):
    """内嵌编辑弹窗：添加/编辑提醒。"""

    def __init__(self, parent=None, title="", remind_time=None,
                 remind_date=None, repeat_type="none",
                 repeat_days="", snooze_min=10):
        super().__init__(parent)
        self.setWindowTitle("提醒")
        self.setMinimumWidth(340)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Title
        layout.addWidget(QLabel("标题："))
        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText("提醒内容...")
        layout.addWidget(self.title_edit)

        # Date (for one-time reminders)
        self.date_label = QLabel("日期：")
        layout.addWidget(self.date_label)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        if remind_date:
            year, month, day = map(int, remind_date.split("-"))
            self.date_edit.setDate(QDate(year, month, day))
        else:
            self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.date_edit)

        # Time
        layout.addWidget(QLabel("时间："))
        self.time_edit = QTimeEdit()
        if remind_time:
            h, m = map(int, remind_time.split(":"))
            self.time_edit.setTime(QTime(h, m))
        self.time_edit.setDisplayFormat("HH:mm")
        layout.addWidget(self.time_edit)

        # Repeat type
        layout.addWidget(QLabel("重复："))
        self.repeat_combo = QComboBox()
        self.repeat_combo.addItems(["不重复", "每天", "每周", "工作日"])
        type_map = {"none": 0, "daily": 1, "weekly": 2, "weekday": 3}
        self.repeat_combo.setCurrentIndex(type_map.get(repeat_type, 0))
        self.repeat_combo.currentIndexChanged.connect(self._on_repeat_changed)
        layout.addWidget(self.repeat_combo)

        # Snooze
        layout.addWidget(QLabel("延后（分钟）："))
        self.snooze_spin = QSpinBox()
        self.snooze_spin.setRange(1, 120)
        self.snooze_spin.setValue(snooze_min)
        layout.addWidget(self.snooze_spin)

        # Buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        # Initial state: show date picker only for one-time (none)
        self._on_repeat_changed(type_map.get(repeat_type, 0))

    def _on_repeat_changed(self, index):
        """Show date picker only for one-time (不重复) reminders."""
        visible = (index == 0)  # 0 = "不重复"
        self.date_label.setVisible(visible)
        self.date_edit.setVisible(visible)

    def get_data(self):
        type_map = {0: "none", 1: "daily", 2: "weekly", 3: "weekday"}
        repeat_type = type_map[self.repeat_combo.currentIndex()]
        return {
            "title": self.title_edit.text().strip(),
            "remind_time": self.time_edit.time().toString("HH:mm"),
            "remind_date": self.date_edit.date().toString("yyyy-MM-dd")
                           if repeat_type == "none" else None,
            "repeat_type": repeat_type,
            "snooze_min": self.snooze_spin.value(),
        }


class ReminderListWidget(QWidget):
    def __init__(self, reminder_engine, parent=None):
        super().__init__(parent)
        self._engine = reminder_engine
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ---- Inline add bar ----
        add_bar = QHBoxLayout()
        add_bar.setSpacing(6)

        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("提醒内容…")
        self._title_input.setStyleSheet(
            "QLineEdit { border:1px solid #ddd; border-radius:4px; "
            "padding:6px 10px; font-size:13px; }"
            "QLineEdit:focus { border-color:#ef5350; }"
        )

        self._repeat_combo = QComboBox()
        self._repeat_combo.addItems(["不重复", "每天", "每周", "工作日"])
        self._repeat_combo.setCurrentIndex(0)
        self._repeat_combo.setFixedWidth(72)
        self._repeat_combo.setStyleSheet(
            "QComboBox { border:1px solid #ddd; border-radius:4px; "
            "padding:4px 6px; font-size:12px; }"
        )
        self._repeat_combo.currentIndexChanged.connect(self._on_add_repeat_changed)

        self._add_date = QDateEdit()
        self._add_date.setCalendarPopup(True)
        self._add_date.setDate(QDate.currentDate())
        self._add_date.setDisplayFormat("MM-dd")
        self._add_date.setMinimumWidth(76)
        self._add_date.setStyleSheet(
            "QDateEdit { border:1px solid #ddd; border-radius:2px; "
            "padding:3px 4px; font-size:12px; min-width:76px; }"
        )

        arrow_style = (
            "QPushButton { border:1px solid #ddd; background:#fafafa; "
            "font-size:10px; padding:0; }"
            "QPushButton:hover { background:#eee; }"
        )
        self._date_prev = QPushButton("◀")
        self._date_prev.setFixedSize(20, 22)
        self._date_prev.setStyleSheet(arrow_style)
        self._date_prev.clicked.connect(lambda: self._shift_add_date(-1))
        self._date_next = QPushButton("▶")
        self._date_next.setFixedSize(20, 22)
        self._date_next.setStyleSheet(arrow_style)
        self._date_next.clicked.connect(lambda: self._shift_add_date(1))

        self._add_time = QTimeEdit()
        self._add_time.setTime(QTime.currentTime())
        self._add_time.setDisplayFormat("HH:mm")
        self._add_time.setMinimumWidth(76)
        self._add_time.setStyleSheet(
            "QTimeEdit { border:1px solid #ddd; border-radius:4px; "
            "padding:3px 4px; font-size:12px; min-width:76px; }"
        )

        add_btn = QPushButton("+")
        add_btn.setFixedWidth(32)
        add_btn.setStyleSheet(
            "QPushButton { background:#ef5350; color:white; border:none; "
            "border-radius:4px; font-size:18px; font-weight:bold; "
            "padding:3px 0; }"
            "QPushButton:hover { background:#e53935; }"
        )
        add_btn.clicked.connect(self._on_add)

        add_bar.addWidget(self._title_input, 1)
        add_bar.addWidget(self._repeat_combo)
        add_bar.addWidget(self._date_prev)
        add_bar.addWidget(self._add_date)
        add_bar.addWidget(self._date_next)
        add_bar.addWidget(self._add_time)
        add_bar.addWidget(add_btn)
        layout.addLayout(add_bar)

        # ---- Card list via QScrollArea ----
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border:none; }")

        self._cards_widget = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(4)
        self._scroll.setWidget(self._cards_widget)
        layout.addWidget(self._scroll, 1)

        self.refresh()

    def refresh(self):
        """从 engine 重新加载所有提醒并重建卡片。"""
        # 彻底清空布局（takeAt 立即移除，deleteLater 延迟释放）
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        reminders = self._engine.get_all_reminders()
        if not reminders:
            empty = QLabel("暂无提醒，点击上方按钮添加")
            empty.setStyleSheet("color:#bbb; font-size:12px; padding:16px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._cards_layout.addWidget(empty)
        else:
            for r in reminders:
                self._cards_layout.addWidget(self._make_card(r))

        self._cards_layout.addStretch()

    # ------------------------------------------------------------------
    # Card builder
    # ------------------------------------------------------------------

    def _make_card(self, reminder: dict) -> QWidget:
        card = QFrame()
        card.setObjectName("reminderCard")
        card.setStyleSheet(
            "QFrame#reminderCard { background:white; border:1px solid #eee; "
            "border-radius:4px; }"
            "QFrame#reminderCard:hover { border-color:#ddd; }"
        )

        row = QHBoxLayout(card)
        row.setContentsMargins(10, 4, 10, 4)
        row.setSpacing(6)

        # Status icon
        enabled = reminder.get("enabled", 1)
        icon_text = "🔔" if enabled else "🔕"
        icon_label = QLabel(icon_text)
        icon_label.setFixedWidth(24)
        icon_label.setStyleSheet("font-size:14px; border:none; background:transparent;")

        # Date label (for one-time reminders)
        repeat_type = reminder.get("repeat_type", "none")
        remind_date = reminder.get("remind_date")
        if repeat_type == "none" and remind_date:
            date_text = f"📅 {remind_date}"
            date_label = QLabel(date_text)
            date_label.setStyleSheet(
                "font-size:11px; color:#888; border:none; background:transparent;"
            )
        else:
            date_label = None

        # Time
        time_label = QLabel(reminder.get("remind_time", ""))
        time_label.setStyleSheet(
            "font-size:13px; font-weight:bold; color:#333; border:none; background:transparent;"
        )

        # Title
        title_label = QLabel(reminder.get("title", ""))
        title_label.setStyleSheet(
            "font-size:13px; color:#555; border:none; background:transparent;"
        )
        title_label.setWordWrap(True)

        # Repeat badge
        repeat_map = {"daily": "每天", "weekly": "每周", "weekday": "工作日"}
        repeat_label_text = repeat_map.get(repeat_type, "")
        if repeat_label_text:
            repeat_badge = QLabel(repeat_label_text)
            repeat_badge.setStyleSheet(
                "font-size:10px; color:#fff; background:#90a4ae; "
                "border-radius:3px; padding:1px 5px;"
            )
        else:
            repeat_badge = None

        # Gather left-side widgets
        row.addWidget(icon_label)
        if date_label:
            row.addWidget(date_label)
        row.addWidget(time_label)
        row.addWidget(title_label, 1)
        if repeat_badge:
            row.addWidget(repeat_badge)

        btn_style = (
            "QPushButton { border:1px solid #ddd; border-radius:3px; "
            "background:#fafafa; font-size:11px; }"
            "QPushButton:hover { background:#eee; }"
        )

        # Toggle button
        toggle_btn = QPushButton("🔕" if enabled else "🔔")
        toggle_btn.setFixedSize(22, 22)
        toggle_btn.setToolTip("禁用" if enabled else "启用")
        toggle_btn.setStyleSheet(btn_style)
        toggle_btn.clicked.connect(lambda: self._on_toggle(reminder["id"]))

        # Edit button
        edit_btn = QPushButton("✎")
        edit_btn.setFixedSize(22, 22)
        edit_btn.setStyleSheet(btn_style)
        edit_btn.clicked.connect(lambda: self._on_edit(reminder["id"]))

        # Delete button
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(22, 22)
        del_btn.setStyleSheet(
            "QPushButton { border:1px solid #ddd; border-radius:3px; "
            "background:#fafafa; font-size:11px; color:#999; }"
            "QPushButton:hover { background:#fce4e4; color:#e53935; }"
        )
        del_btn.clicked.connect(lambda: self._on_delete(reminder["id"]))

        row.addWidget(toggle_btn)
        row.addWidget(edit_btn)
        row.addWidget(del_btn)

        return card

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_add_repeat_changed(self, index):
        """Enable date controls only for 不重复; disable otherwise."""
        enabled = (index == 0)
        self._date_prev.setEnabled(enabled)
        self._add_date.setEnabled(enabled)
        self._date_next.setEnabled(enabled)

    def _shift_add_date(self, days):
        d = self._add_date.date().addDays(days)
        self._add_date.setDate(d)

    def _on_add(self):
        title = self._title_input.text().strip()
        if not title:
            return
        repeat_type = ["none", "daily", "weekly", "weekday"][self._repeat_combo.currentIndex()]
        remind_date = self._add_date.date().toString("yyyy-MM-dd") if repeat_type == "none" else None
        remind_time = self._add_time.time().toString("HH:mm")
        self._engine.add_reminder(
            title=title,
            remind_time=remind_time,
            remind_date=remind_date,
            repeat_type=repeat_type,
            snooze_min=10,
        )
        logger.info("Reminder added: title=%s, time=%s, repeat=%s", title, remind_time, repeat_type)
        self._title_input.clear()
        self.refresh()

    def _on_edit(self, reminder_id):
        r = self._engine.db.get_reminder(reminder_id)
        if not r:
            return
        dlg = _ReminderEditDialog(
            self, title=r["title"], remind_time=r["remind_time"],
            remind_date=r.get("remind_date"),
            repeat_type=r.get("repeat_type", "none"),
            repeat_days=r.get("repeat_days", ""),
            snooze_min=r.get("snooze_min", 10),
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if not data["title"]:
                return
            self._engine.update_reminder(reminder_id, **data)
            logger.info("Reminder updated: id=%d", reminder_id)
            self.refresh()

    def _on_delete(self, reminder_id):
        reply = QMessageBox.question(
            self, "删除提醒", "确定要删除这个提醒吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._engine.delete_reminder(reminder_id)
            logger.info("Reminder deleted: id=%d", reminder_id)
            self.refresh()

    def _on_toggle(self, reminder_id):
        r = self._engine.db.get_reminder(reminder_id)
        if r:
            self._engine.update_reminder(reminder_id, enabled=0 if r["enabled"] else 1)
            logger.debug("Reminder toggled: id=%d", reminder_id)
            self.refresh()
