"""
ReminderDialog — 提醒管理弹窗薄壳 (TASK-13)

内嵌 ReminderListWidget 作为唯一子控件。
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout
from src.reminder_list_widget import ReminderListWidget


class ReminderDialog(QDialog):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⏰ 提醒管理")
        self.resize(480, 400)
        self.setModal(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self._reminder_widget = ReminderListWidget(engine, self)
        layout.addWidget(self._reminder_widget)
