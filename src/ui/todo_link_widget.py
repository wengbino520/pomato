"""TodoLinkWidget — 可复用的"关联待办"下拉组件。

供 PopupWindow / EditEntryDialog / AddEntryDialog 共用，
包含一个 QComboBox（待办下拉）+ QCheckBox（标记完成）。

(CD-01: 消除三处重复代码)
"""

from datetime import date

from PyQt6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QWidget

from src.services.logger import get_logger

logger = get_logger(__name__)


class TodoLinkWidget(QWidget):
    """关联待办：下拉选择 + 标记完成勾选框。

    用法::

        self._todo_link = TodoLinkWidget(reminder_engine, parent=self)
        layout.addWidget(self._todo_link)
        ...
        todo_id, mark_done = self._todo_link.get_todo_info()
    """

    def __init__(self, reminder_engine, current_todo_id: int = 0, parent=None):
        super().__init__(parent)
        self._reminder_engine = reminder_engine
        self._current_todo_id = current_todo_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel("关联待办：")
        label.setStyleSheet("font-size:12px; color:#666;")
        layout.addWidget(label)

        self._combo = QComboBox()
        self._combo.addItem("（不关联）", 0)
        self._combo.setStyleSheet(
            "QComboBox { border:1px solid #ddd; border-radius:4px; "
            "padding:4px 8px; font-size:12px; }"
        )
        layout.addWidget(self._combo, 1)

        self._done_cb = QCheckBox("标记完成")
        self._done_cb.setStyleSheet("font-size:12px; color:#666;")
        layout.addWidget(self._done_cb)

        # 加载待办列表
        self.load_todos()

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def load_todos(self):
        """从 ReminderEngine 重新加载未完成的待办列表。"""
        if not self._reminder_engine:
            self.setVisible(False)
            return

        today_str = date.today().isoformat()
        try:
            todos = self._reminder_engine.get_todos(
                date_str=today_str, include_done=False
            )
        except Exception:
            logger.debug("Failed to load todos", exc_info=True)
            self.setVisible(False)
            return

        # 保留第一项"（不关联）"，清除其余
        while self._combo.count() > 1:
            self._combo.removeItem(self._combo.count() - 1)

        for t in todos:
            self._combo.addItem(t["title"], t["id"])
            if t["id"] == self._current_todo_id:
                self._combo.setCurrentIndex(self._combo.count() - 1)

        self.setVisible(True)

    def get_todo_info(self) -> tuple[int, bool]:
        """返回 (todo_id, 是否标记完成)。0 表示未关联。"""
        if not self._reminder_engine:
            return 0, False
        todo_id = self._combo.currentData() or 0
        mark_done = self._done_cb.isChecked()
        return todo_id, mark_done
