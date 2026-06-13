"""
TodoListWidget — 自包含待办列表组件 (TASK-09)
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLineEdit, QComboBox, QDateEdit, QPushButton, QLabel,
    QCheckBox, QFrame, QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import QDate

from src.services.logger import get_logger

logger = get_logger(__name__)


class TodoListWidget(QWidget):
    todo_added = pyqtSignal(str, int, str, str)  # title, priority, due_date, note

    def __init__(self, reminder_engine, parent=None):
        super().__init__(parent)
        self._engine = reminder_engine
        self._setup_ui()
        self._engine.todos_changed.connect(self.refresh)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ---- 添加栏 ----
        add_bar = QHBoxLayout()
        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("输入新待办...")
        self._title_input.setStyleSheet(
            "QLineEdit { border:1px solid #ddd; border-radius:4px; "
            "padding:6px 10px; font-size:13px; }"
            "QLineEdit:focus { border-color:#ef5350; }"
        )

        self._priority_combo = QComboBox()
        self._priority_combo.addItems(["低", "中", "高"])
        self._priority_combo.setCurrentIndex(1)
        self._priority_combo.setFixedWidth(52)
        self._priority_combo.setStyleSheet(
            "QComboBox { border:1px solid #ddd; border-radius:4px; "
            "padding:3px 4px; font-size:12px; }"
        )

        self._due_date = QDateEdit()
        self._due_date.setCalendarPopup(True)
        self._due_date.setDate(QDate.currentDate())
        self._due_date.setDisplayFormat("MM-dd")
        self._due_date.setMinimumWidth(76)
        self._due_date.setStyleSheet(
            "QDateEdit { border:1px solid #ddd; border-radius:2px; "
            "padding:3px 4px; font-size:12px; min-width:76px; }"
        )

        arrow_style = (
            "QPushButton { border:1px solid #ddd; background:#fafafa; "
            "font-size:10px; padding:0; }"
            "QPushButton:hover { background:#eee; }"
        )
        date_prev = QPushButton("◀")
        date_prev.setFixedSize(20, 22)
        date_prev.setStyleSheet(arrow_style)
        date_prev.clicked.connect(lambda: self._shift_date(-1))
        date_next = QPushButton("▶")
        date_next.setFixedSize(20, 22)
        date_next.setStyleSheet(arrow_style)
        date_next.clicked.connect(lambda: self._shift_date(1))

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
        add_bar.addWidget(self._priority_combo)
        add_bar.addWidget(date_prev)
        add_bar.addWidget(self._due_date)
        add_bar.addWidget(date_next)
        add_bar.addWidget(add_btn)
        layout.addLayout(add_bar)

        # ---- 待办列表 ----
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border:none; }")
        self._cards_widget = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(4)
        self._scroll.setWidget(self._cards_widget)
        layout.addWidget(self._scroll, 1)

    def refresh(self):
        """从 engine 重新加载待办并重建卡片。"""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        todos = self._engine.get_todos(date_str=today, include_done=True)

        # 彻底清空布局（takeAt 立即移除，deleteLater 延迟释放）
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not todos:
            empty = QLabel("暂无待办，添加一条吧 ✨")
            empty.setStyleSheet("color:#bbb; font-size:12px; padding:16px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._cards_layout.addWidget(empty)
        else:
            for todo in todos:
                self._cards_layout.addWidget(self._make_card(todo))

        self._cards_layout.addStretch()

    # ------------------------------------------------------------------
    # Card builder
    # ------------------------------------------------------------------

    def _make_card(self, todo: dict) -> QWidget:
        card = QFrame()
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setStyleSheet(
            "QFrame { background:white; border:1px solid #eee; "
            "border-radius:4px; padding:2px; }"
            "QFrame:hover { border-color:#ddd; }"
        )

        row = QHBoxLayout(card)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(8)

        # Priority color bar (left edge)
        color_bar = QWidget()
        colors = {2: "#ef5350", 1: "#ff9800", 0: "#9e9e9e"}
        bar_color = colors.get(todo.get("priority", 1), "#9e9e9e")
        color_bar.setFixedWidth(4)
        color_bar.setStyleSheet(f"background:{bar_color}; border-radius:2px;")
        color_bar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        # Checkbox
        cb = QCheckBox()
        cb.setChecked(todo.get("status") == "done")
        cb.toggled.connect(lambda checked, tid=todo["id"]: self._on_toggle(tid, checked))

        # Title
        title = todo.get("title", "")
        if todo.get("status") == "done":
            title = f"<s style='color:#bbb'>{title}</s>"
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size:13px; color:#333;")
        title_label.setTextFormat(Qt.TextFormat.RichText)
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Priority badge
        priority_map = {2: ("高", "#ef5350"), 1: ("中", "#ff9800"), 0: ("低", "#9e9e9e")}
        prio_text, prio_bg = priority_map.get(todo.get("priority", 1), ("中", "#ff9800"))
        prio_badge = QLabel(prio_text)
        prio_badge.setStyleSheet(
            f"font-size:10px; color:#fff; background:{prio_bg}; "
            "border-radius:3px; padding:1px 5px;"
        )

        # Due date
        due = todo.get("due_date", "")
        row.addWidget(color_bar)
        row.addWidget(cb)
        row.addWidget(title_label, 1)
        row.addWidget(prio_badge)
        if due:
            due_label = QLabel(due)
            due_label.setStyleSheet("font-size:11px; color:#999;")
            row.addWidget(due_label)

        # Edit / Delete buttons
        edit_btn = QPushButton("✎")
        edit_btn.setFixedSize(24, 24)
        edit_btn.setStyleSheet(
            "QPushButton { background:transparent; border:none; "
            "font-size:13px; color:#bbb; }"
            "QPushButton:hover { color:#ef5350; }"
        )
        edit_btn.clicked.connect(lambda _, tid=todo["id"]: self._on_edit(tid))

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(24, 24)
        del_btn.setStyleSheet(
            "QPushButton { background:transparent; border:none; "
            "font-size:13px; color:#bbb; }"
            "QPushButton:hover { color:#c62828; }"
        )
        del_btn.clicked.connect(lambda _, tid=todo["id"]: self._on_delete(tid))

        row.addWidget(edit_btn)
        row.addWidget(del_btn)

        return card

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _shift_date(self, days):
        d = self._due_date.date().addDays(days)
        self._due_date.setDate(d)

    def _on_add(self):
        title = self._title_input.text().strip()
        if not title:
            return
        priority = self._priority_combo.currentIndex()
        due_date = self._due_date.date().toString("yyyy-MM-dd")
        self._engine.add_todo(title, priority=priority, due_date=due_date)
        logger.info("Todo added: title=%s, priority=%d", title, priority)
        self.todo_added.emit(title, priority, due_date, "")
        self._title_input.clear()
        self._title_input.setFocus()

    def _on_toggle(self, todo_id: int, checked: bool):
        status = "done" if checked else "pending"
        self._engine.update_todo(todo_id, status=status)
        logger.debug("Todo toggled: id=%d, status=%s", todo_id, status)

    def _on_edit(self, todo_id: int):
        todo = self._engine.db.get_todo(todo_id)
        if not todo:
            return
        # Simple inline edit: put title in input and update on submit
        self._title_input.setText(todo.get("title", ""))
        self._priority_combo.setCurrentIndex(todo.get("priority", 1))
        if todo.get("due_date"):
            self._due_date.setDate(QDate.fromString(todo["due_date"], "yyyy-MM-dd"))

        # Replace add button with update
        self._title_input.setFocus()

    def _on_delete(self, todo_id: int):
        reply = QMessageBox.question(
            self, "删除待办", "确定要删除这个待办吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._engine.delete_todo(todo_id)
            logger.info("Todo deleted: id=%d", todo_id)
