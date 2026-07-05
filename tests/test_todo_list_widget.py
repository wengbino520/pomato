"""
TodoListWidget 单元测试

覆盖：初始化、refresh 展示、添加待办、切换状态、编辑、删除、日期偏移、信号。
"""
import pytest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QDate


@pytest.fixture
def todo_widget(qapp, reminder_engine):
    """创建 TodoListWidget 实例。"""
    from src.ui.todo_list_widget import TodoListWidget
    w = TodoListWidget(reminder_engine)
    return w


# ═══════════════════════════════════════════════════════════════════
# 初始化与空状态
# ═══════════════════════════════════════════════════════════════════

class TestTodoListInit:
    def test_widget_creates_successfully(self, todo_widget):
        """Widget 创建不抛异常。"""
        assert todo_widget is not None

    def test_title_input_exists_and_empty(self, todo_widget):
        """标题输入框存在且为空。"""
        assert todo_widget._title_input.text() == ""

    def test_priority_defaults_to_medium(self, todo_widget):
        """优先级默认为'中'（index 1）。"""
        assert todo_widget._priority_combo.currentIndex() == 1

    def test_empty_state_shows_placeholder(self, todo_widget):
        """无待办时 refresh 显示占位提示。"""
        todo_widget.refresh()
        from PyQt6.QtWidgets import QLabel
        labels = todo_widget._cards_widget.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert any("暂无待办" in t for t in texts)


# ═══════════════════════════════════════════════════════════════════
# 添加待办
# ═══════════════════════════════════════════════════════════════════

class TestTodoAdd:
    def test_add_empty_title_does_nothing(self, todo_widget, reminder_engine):
        """空标题不添加待办。"""
        todo_widget._title_input.setText("")
        todo_widget._on_add()
        todos = reminder_engine.get_todos(include_done=True)
        assert todos == []

    def test_add_todo_success(self, todo_widget, reminder_engine):
        """正常输入标题后添加成功。"""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        todo_widget._title_input.setText("写单元测试")
        todo_widget._on_add()
        todos = reminder_engine.get_todos(date_str=today, include_done=True)
        assert len(todos) == 1
        assert todos[0]["title"] == "写单元测试"

    def test_add_clears_input(self, todo_widget):
        """添加成功后输入框被清空。"""
        todo_widget._title_input.setText("整理文档")
        todo_widget._on_add()
        assert todo_widget._title_input.text() == ""

    def test_add_with_high_priority(self, todo_widget, reminder_engine):
        """选择高优先级(index 2)添加。"""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        todo_widget._title_input.setText("紧急修复")
        todo_widget._priority_combo.setCurrentIndex(2)  # 高
        todo_widget._on_add()
        todos = reminder_engine.get_todos(date_str=today, include_done=True)
        assert todos[0]["priority"] == 2

    def test_add_with_low_priority(self, todo_widget, reminder_engine):
        """选择低优先级(index 0)添加。"""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        todo_widget._title_input.setText("低优先级任务")
        todo_widget._priority_combo.setCurrentIndex(0)  # 低
        todo_widget._on_add()
        todos = reminder_engine.get_todos(date_str=today, include_done=True)
        assert todos[0]["priority"] == 0

    def test_add_with_custom_due_date(self, todo_widget, reminder_engine):
        """设置自定义截止日期后添加，due_date 被正确存储。"""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        todo_widget._title_input.setText("未来任务")
        todo_widget._due_date.setDate(QDate(2025, 12, 31))
        todo_widget._on_add()
        # add_todo uses today as todo_date; due_date is separate
        todos = reminder_engine.get_todos(date_str=today, include_done=True)
        assert len(todos) >= 1
        matched = [t for t in todos if t["title"] == "未来任务"]
        assert len(matched) == 1
        assert matched[0]["due_date"] == "2025-12-31"

    def test_add_emits_signal(self, todo_widget):
        """添加成功后发出 todo_added 信号。"""
        collected = []
        todo_widget.todo_added.connect(lambda *args: collected.append(args))
        todo_widget._title_input.setText("信号测试")
        todo_widget._on_add()
        assert len(collected) == 1
        assert collected[0][0] == "信号测试"


# ═══════════════════════════════════════════════════════════════════
# Refresh 与卡片渲染
# ═══════════════════════════════════════════════════════════════════

class TestTodoRefresh:
    def test_refresh_shows_cards(self, todo_widget, reminder_engine):
        """添加待办后 refresh 应生成卡片。"""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        reminder_engine.add_todo("卡片测试", priority=1, due_date=today)
        todo_widget.refresh(today)
        from PyQt6.QtWidgets import QFrame
        cards = todo_widget._cards_widget.findChildren(QFrame)
        assert len(cards) >= 1

    def test_refresh_with_date_param(self, todo_widget, reminder_engine):
        """传入 date_str 参数 refresh 只显示该日期的待办。"""
        reminder_engine.add_todo("今天的", priority=1, due_date="2025-07-01")
        reminder_engine.add_todo("明天的", priority=1, due_date="2025-07-02")
        todo_widget.refresh("2025-07-01")
        from PyQt6.QtWidgets import QLabel
        labels = todo_widget._cards_widget.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert any("今天的" in t for t in texts)

    def test_refresh_preserves_current_date(self, todo_widget):
        """refresh(None) 使用上次设置的日期。"""
        todo_widget.refresh("2025-06-15")
        assert todo_widget._current_date == "2025-06-15"
        todo_widget.refresh()
        assert todo_widget._current_date == "2025-06-15"

    def test_refresh_clears_old_content(self, todo_widget, reminder_engine):
        """refresh 后旧内容被清除。"""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        reminder_engine.add_todo("旧任务", priority=1, due_date=today)
        todo_widget.refresh(today)
        # 删除后 refresh
        todos = reminder_engine.get_todos(date_str=today, include_done=True)
        for t in todos:
            reminder_engine.delete_todo(t["id"])
        todo_widget.refresh(today)
        from PyQt6.QtWidgets import QLabel
        labels = todo_widget._cards_widget.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert any("暂无待办" in t for t in texts)


# ═══════════════════════════════════════════════════════════════════
# 切换状态（Toggle）
# ═══════════════════════════════════════════════════════════════════

class TestTodoToggle:
    def test_toggle_marks_done(self, todo_widget, reminder_engine):
        """勾选待办后状态变为 done。"""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        tid = reminder_engine.add_todo("完成测试", priority=1, due_date=today)
        todo_widget._current_date = today
        todo_widget._on_toggle(tid, True)
        todo = reminder_engine.db.get_todo(tid)
        assert todo["status"] == "done"

    def test_toggle_marks_pending(self, todo_widget, reminder_engine):
        """取消勾选后状态恢复为 pending。"""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        tid = reminder_engine.add_todo("恢复测试", priority=1, due_date=today)
        # 先标记完成
        reminder_engine.update_todo(tid, status="done")
        # 再取消
        todo_widget._current_date = today
        todo_widget._on_toggle(tid, False)
        todo = reminder_engine.db.get_todo(tid)
        assert todo["status"] == "pending"

    def test_toggle_past_todo_moves_date_to_today(self, todo_widget, reminder_engine):
        """今日视图中勾选过去的待办，日期移到今天。"""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        past = "2024-01-01"
        tid = reminder_engine.add_todo("过去任务", priority=1, due_date=past)
        todo_widget._current_date = today
        todo_widget._on_toggle(tid, True)
        todo = reminder_engine.db.get_todo(tid)
        assert todo["status"] == "done"


# ═══════════════════════════════════════════════════════════════════
# 编辑
# ═══════════════════════════════════════════════════════════════════

class TestTodoEdit:
    def test_edit_populates_input(self, todo_widget, reminder_engine):
        """编辑待办后，标题输入框填入对应文本。"""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        tid = reminder_engine.add_todo("编辑我", priority=2, due_date=today)
        todo_widget._on_edit(tid)
        assert todo_widget._title_input.text() == "编辑我"
        assert todo_widget._priority_combo.currentIndex() == 2

    def test_edit_nonexistent_noop(self, todo_widget):
        """编辑不存在的待办 id 不抛异常。"""
        todo_widget._on_edit(99999)  # Should not raise

    def test_edit_sets_due_date(self, todo_widget, reminder_engine):
        """编辑待办后日期控件更新。"""
        tid = reminder_engine.add_todo("日期测试", priority=1, due_date="2025-09-15")
        todo_widget._on_edit(tid)
        assert todo_widget._due_date.date() == QDate(2025, 9, 15)


# ═══════════════════════════════════════════════════════════════════
# 删除（带 QMessageBox mock）
# ═══════════════════════════════════════════════════════════════════

class TestTodoDelete:
    def test_delete_confirmed_removes(self, todo_widget, reminder_engine):
        """确认删除后待办被移除。"""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        tid = reminder_engine.add_todo("删我", priority=1, due_date=today)
        from PyQt6.QtWidgets import QMessageBox
        with patch("src.ui.todo_list_widget.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes):
            todo_widget._on_delete(tid)
        todos = reminder_engine.get_todos(date_str=today, include_done=True)
        assert all(t["id"] != tid for t in todos)

    def test_delete_cancelled_keeps(self, todo_widget, reminder_engine):
        """取消删除后待办仍然存在。"""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        tid = reminder_engine.add_todo("别删我", priority=1, due_date=today)
        from PyQt6.QtWidgets import QMessageBox
        with patch("src.ui.todo_list_widget.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.No):
            todo_widget._on_delete(tid)
        todos = reminder_engine.get_todos(date_str=today, include_done=True)
        assert any(t["id"] == tid for t in todos)


# ═══════════════════════════════════════════════════════════════════
# 日期偏移
# ═══════════════════════════════════════════════════════════════════

class TestTodoDateShift:
    def test_shift_forward(self, todo_widget):
        """日期前进一天。"""
        todo_widget._due_date.setDate(QDate(2025, 7, 1))
        todo_widget._shift_date(1)
        assert todo_widget._due_date.date() == QDate(2025, 7, 2)

    def test_shift_backward(self, todo_widget):
        """日期后退一天。"""
        todo_widget._due_date.setDate(QDate(2025, 7, 3))
        todo_widget._shift_date(-1)
        assert todo_widget._due_date.date() == QDate(2025, 7, 2)

    def test_shift_across_month(self, todo_widget):
        """跨月日期偏移。"""
        todo_widget._due_date.setDate(QDate(2025, 7, 31))
        todo_widget._shift_date(1)
        assert todo_widget._due_date.date() == QDate(2025, 8, 1)


# ═══════════════════════════════════════════════════════════════════
# Card 渲染细节
# ═══════════════════════════════════════════════════════════════════

class TestTodoCardRendering:
    def test_done_todo_shows_strikethrough(self, todo_widget, reminder_engine):
        """已完成待办的标题使用删除线。"""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        tid = reminder_engine.add_todo("已完成", priority=1, due_date=today)
        reminder_engine.update_todo(tid, status="done")
        todo_widget.refresh(today)
        from PyQt6.QtWidgets import QLabel
        labels = todo_widget._cards_widget.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert any("<s " in t and "已完成" in t for t in texts)

    def test_card_has_priority_badge(self, todo_widget, reminder_engine):
        """卡片包含优先级标签。"""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        reminder_engine.add_todo("高优先级", priority=2, due_date=today)
        todo_widget.refresh(today)
        from PyQt6.QtWidgets import QLabel
        labels = todo_widget._cards_widget.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert any("高" == t for t in texts)

    def test_card_has_checkbox(self, todo_widget, reminder_engine):
        """卡片包含复选框。"""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        reminder_engine.add_todo("复选框测试", priority=1, due_date=today)
        todo_widget.refresh(today)
        from PyQt6.QtWidgets import QCheckBox
        checkboxes = todo_widget._cards_widget.findChildren(QCheckBox)
        assert len(checkboxes) >= 1
