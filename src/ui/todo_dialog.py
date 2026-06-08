"""
TodoDialog — 待办弹窗薄壳 (TASK-12)

内嵌 TodoListWidget 作为唯一子控件。
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout
from src.ui.todo_list_widget import TodoListWidget


class TodoDialog(QDialog):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 待办事项")
        self.resize(480, 500)
        self.setModal(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self._todo_widget = TodoListWidget(engine, self)
        layout.addWidget(self._todo_widget)

        self._todo_widget.refresh()
