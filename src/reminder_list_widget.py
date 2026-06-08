"""
ReminderListWidget — 自包含提醒列表组件 (TASK-10)
"""
from PyQt6.QtCore import Qt, QTime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel,
    QDialog, QDialogButtonBox, QLineEdit, QTimeEdit,
    QComboBox, QSpinBox, QMessageBox,
)


class _ReminderEditDialog(QDialog):
    """内嵌编辑弹窗：添加/编辑提醒。"""

    def __init__(self, parent=None, title="", remind_time=None,
                 repeat_type="none", repeat_days="", snooze_min=10):
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

    def get_data(self):
        type_map = {0: "none", 1: "daily", 2: "weekly", 3: "weekday"}
        return {
            "title": self.title_edit.text().strip(),
            "remind_time": self.time_edit.time().toString("HH:mm"),
            "repeat_type": type_map[self.repeat_combo.currentIndex()],
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

        # ---- Add button ----
        add_bar = QHBoxLayout()
        add_btn = QPushButton("+ 添加提醒")
        add_btn.setStyleSheet(
            "QPushButton { background:#ef5350; color:white; border:none; "
            "border-radius:4px; padding:6px 16px; font-size:13px; }"
            "QPushButton:hover { background:#e53935; }"
        )
        add_btn.clicked.connect(self._on_add)
        add_bar.addStretch()
        add_bar.addWidget(add_btn)
        layout.addLayout(add_bar)

        # ---- List ----
        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget { border:1px solid #eee; border-radius:4px; }"
            "QListWidget::item { padding:6px 8px; }"
            "QListWidget::item:hover { background:#fafafa; }"
        )
        layout.addWidget(self._list, 1)

        self.refresh()

    def refresh(self):
        """从 engine 重新加载所有提醒。"""
        self._list.clear()
        reminders = self._engine.get_all_reminders()
        if not reminders:
            empty = QListWidgetItem("暂无提醒，点击上方按钮添加")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(empty)
            return

        for r in reminders:
            enabled = r.get("enabled", 1)
            repeat_map = {"none": "", "daily": "· 每天", "weekly": "· 每周",
                          "weekday": "· 工作日"}
            repeat_label = repeat_map.get(r.get("repeat_type", "none"), "")
            status_icon = "🔔" if enabled else "🔕"
            text = f"{status_icon}  {r['remind_time']}  {r['title']}  {repeat_label}"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, r["id"])
            if not enabled:
                item.setForeground(Qt.GlobalColor.gray)
            self._list.addItem(item)

        self._list.setCurrentRow(-1)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_add(self):
        dlg = _ReminderEditDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if not data["title"]:
                return
            self._engine.add_reminder(**data)
            self.refresh()

    def _on_edit(self, reminder_id):
        r = self._engine.db.get_reminder(reminder_id)
        if not r:
            return
        dlg = _ReminderEditDialog(
            self, title=r["title"], remind_time=r["remind_time"],
            repeat_type=r.get("repeat_type", "none"),
            repeat_days=r.get("repeat_days", ""),
            snooze_min=r.get("snooze_min", 10),
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if not data["title"]:
                return
            self._engine.update_reminder(reminder_id, **data)
            self.refresh()

    def _on_delete(self, reminder_id):
        reply = QMessageBox.question(
            self, "删除提醒", "确定要删除这个提醒吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._engine.delete_reminder(reminder_id)
            self.refresh()

    def _on_toggle(self, reminder_id):
        r = self._engine.db.get_reminder(reminder_id)
        if r:
            self._engine.update_reminder(reminder_id, enabled=0 if r["enabled"] else 1)
            self.refresh()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event):
        item = self._list.currentItem()
        if not item:
            return
        reminder_id = item.data(Qt.ItemDataRole.UserRole)
        if reminder_id is None:
            return

        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)

        r = self._engine.db.get_reminder(reminder_id)
        if r:
            toggle_text = "🔕 禁用" if r.get("enabled", 1) else "🔔 启用"
            menu.addAction(toggle_text, lambda: self._on_toggle(reminder_id))

        menu.addAction("✎ 编辑", lambda: self._on_edit(reminder_id))
        menu.addSeparator()
        menu.addAction("✕ 删除", lambda: self._on_delete(reminder_id))
        menu.exec(event.globalPos())
