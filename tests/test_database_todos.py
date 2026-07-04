"""
TASK-22: 数据库待办方法测试
tests/test_database_todos.py
"""
from datetime import datetime


class TestAddTodo:
    """add_todo 基本正确性。"""

    def test_add_todo_returns_positive_id(self, tmp_db):
        tid = tmp_db.add_todo("测试待办")
        assert isinstance(tid, int)
        assert tid > 0

    def test_add_todo_with_priority_and_due_date(self, tmp_db):
        tid = tmp_db.add_todo("高优任务", priority=2, due_date="2026-06-15")
        todo = tmp_db.get_todo(tid)
        assert todo["title"] == "高优任务"
        assert todo["priority"] == 2
        assert todo["due_date"] == "2026-06-15"
        assert todo["status"] == "pending"

    def test_add_todo_defaults(self, tmp_db):
        tid = tmp_db.add_todo("默认值测试")
        todo = tmp_db.get_todo(tid)
        assert todo["priority"] == 1
        assert todo["status"] == "pending"
        assert todo["note"] == ""
        assert todo["sort_order"] == 0

    def test_add_todo_with_note(self, tmp_db):
        tid = tmp_db.add_todo("带备注", note="这是一段备注文字")
        todo = tmp_db.get_todo(tid)
        assert todo["note"] == "这是一段备注文字"

    def test_add_todo_with_explicit_todo_date(self, tmp_db):
        tid = tmp_db.add_todo("特定日期", todo_date="2026-06-10")
        todo = tmp_db.get_todo(tid)
        assert todo["todo_date"] == "2026-06-10"

    def test_add_todo_todo_date_defaults_to_today(self, tmp_db):
        tid = tmp_db.add_todo("今天")
        today = datetime.now().strftime("%Y-%m-%d")
        todo = tmp_db.get_todo(tid)
        assert todo["todo_date"] == today


class TestGetTodos:
    """get_todos 查询正确性。"""

    def test_get_todos_returns_list(self, tmp_db):
        assert tmp_db.get_todos() == []

    def test_get_todos_by_date(self, tmp_db):
        tmp_db.add_todo("A", todo_date="2026-06-01")
        tmp_db.add_todo("B", todo_date="2026-06-02")
        assert len(tmp_db.get_todos(date_str="2026-06-01")) == 1
        assert len(tmp_db.get_todos(date_str="2026-06-02")) == 1

    def test_get_todos_sorted_by_priority_desc(self, tmp_db):
        tmp_db.add_todo("低", priority=0, todo_date="2026-06-01")
        tmp_db.add_todo("高", priority=2, todo_date="2026-06-01")
        tmp_db.add_todo("中", priority=1, todo_date="2026-06-01")
        todos = tmp_db.get_todos(date_str="2026-06-01")
        assert [t["title"] for t in todos] == ["高", "中", "低"]

    def test_get_todos_excludes_done_when_include_done_false(self, tmp_db):
        tid = tmp_db.add_todo("待完成", todo_date="2026-06-01")
        tmp_db.add_todo("已完成", todo_date="2026-06-01")
        # Mark second as done
        tmp_db.update_todo(tmp_db.add_todo("T", todo_date="2026-06-01"), status="done")
        todos = tmp_db.get_todos(date_str="2026-06-01", include_done=False)
        titles = [t["title"] for t in todos]
        assert "待完成" in titles
        # All should be non-done
        assert all(t["status"] != "done" for t in todos)

    def test_get_todos_includes_done_by_default(self, tmp_db):
        tid = tmp_db.add_todo("Done", todo_date="2026-06-01")
        tmp_db.update_todo(tid, status="done")
        todos = tmp_db.get_todos(date_str="2026-06-01")
        assert len(todos) == 1


class TestGetTodo:
    """get_todo 单条查询。"""

    def test_get_todo_returns_dict(self, tmp_db):
        tid = tmp_db.add_todo("X")
        todo = tmp_db.get_todo(tid)
        assert isinstance(todo, dict)
        assert todo["title"] == "X"

    def test_get_todo_returns_none_for_missing(self, tmp_db):
        assert tmp_db.get_todo(99999) is None


class TestUpdateTodo:
    """update_todo 修改正确性。"""

    def test_update_title(self, tmp_db):
        tid = tmp_db.add_todo("旧标题")
        tmp_db.update_todo(tid, title="新标题")
        assert tmp_db.get_todo(tid)["title"] == "新标题"

    def test_update_status(self, tmp_db):
        tid = tmp_db.add_todo("任务")
        tmp_db.update_todo(tid, status="done")
        assert tmp_db.get_todo(tid)["status"] == "done"

    def test_update_multiple_fields(self, tmp_db):
        tid = tmp_db.add_todo("多字段")
        tmp_db.update_todo(tid, priority=2, due_date="2026-12-31", note="备注")
        t = tmp_db.get_todo(tid)
        assert t["priority"] == 2
        assert t["due_date"] == "2026-12-31"
        assert t["note"] == "备注"

    def test_update_ignores_unknown_fields(self, tmp_db):
        tid = tmp_db.add_todo("X")
        tmp_db.update_todo(tid, unknown_field="bad")  # should not crash
        assert tmp_db.get_todo(tid) is not None

    def test_update_noop_with_empty_kwargs(self, tmp_db):
        tid = tmp_db.add_todo("X")
        tmp_db.update_todo(tid)  # should not crash
        assert tmp_db.get_todo(tid)["title"] == "X"


class TestDeleteTodo:
    """delete_todo 删除。"""

    def test_delete_todo_removes_record(self, tmp_db):
        tid = tmp_db.add_todo("待删除")
        tmp_db.delete_todo(tid)
        assert tmp_db.get_todo(tid) is None

    def test_delete_nonexistent_todo_no_error(self, tmp_db):
        tmp_db.delete_todo(99999)  # should not raise


class TestReorderTodos:
    """reorder_todos 排序。"""

    def test_reorder_updates_sort_order(self, tmp_db):
        id1 = tmp_db.add_todo("A", todo_date="2026-06-01")
        id2 = tmp_db.add_todo("B", todo_date="2026-06-01")
        id3 = tmp_db.add_todo("C", todo_date="2026-06-01")

        tmp_db.reorder_todos([id3, id1, id2])
        todos = tmp_db.get_todos(date_str="2026-06-01")
        assert [t["id"] for t in todos] == [id3, id1, id2]

    def test_reorder_empty_list_no_error(self, tmp_db):
        tmp_db.reorder_todos([])  # should not raise


class TestEdgeCases:
    """边界情况。"""

    def test_empty_title_allowed(self, tmp_db):
        tid = tmp_db.add_todo("")
        assert tmp_db.get_todo(tid)["title"] == ""

    def test_very_long_title(self, tmp_db):
        long_title = "A" * 500
        tid = tmp_db.add_todo(long_title)
        assert len(tmp_db.get_todo(tid)["title"]) == 500


class TestGetTodosByDateRange:
    """D2: get_todos_by_date_range() 按日期范围返回待办。"""

    def test_returns_todos_in_range(self, tmp_db):
        tmp_db.add_todo("周一事", todo_date="2026-06-01")
        tmp_db.add_todo("周三事", todo_date="2026-06-03")
        tmp_db.add_todo("周五事", todo_date="2026-06-05")
        tmp_db.add_todo("上周日", todo_date="2026-05-31")  # 范围外
        tmp_db.add_todo("范围外后", todo_date="2026-06-08")  # 范围外

        result = tmp_db.get_todos_by_date_range("2026-06-01", "2026-06-07")
        titles = [t["title"] for t in result]
        assert "周一事" in titles
        assert "周三事" in titles
        assert "周五事" in titles
        assert "上周日" not in titles
        assert "范围外后" not in titles

    def test_empty_range_returns_empty(self, tmp_db):
        tmp_db.add_todo("测试", todo_date="2026-06-01")
        result = tmp_db.get_todos_by_date_range("2025-01-01", "2025-01-05")
        assert result == []

    def test_includes_done_todos(self, tmp_db):
        tid = tmp_db.add_todo("已完成", todo_date="2026-06-03")
        tmp_db.update_todo(tid, status="done")
        result = tmp_db.get_todos_by_date_range("2026-06-01", "2026-06-07")
        assert any(t["title"] == "已完成" and t["status"] == "done" for t in result)

    def test_accumulates_uncompleted_when_end_is_today(self, tmp_db):
        """end_date 为今天时，纳入历史未完成待办（与 get_todos 今日逻辑一致）。"""
        from datetime import date as dt_date, timedelta

        today = dt_date.today()
        monday = today - timedelta(days=today.weekday())
        long_ago = (today - timedelta(days=30)).isoformat()

        # 插入一个很久以前的未完成待办
        tmp_db.add_todo("旧未完成", todo_date=long_ago)
        # 插入一个很久以前但已完成的待办
        tid_done = tmp_db.add_todo("旧已完成", todo_date=long_ago)
        tmp_db.update_todo(tid_done, status="done")

        # end_date 为今天（不是周日），触发历史累积
        result = tmp_db.get_todos_by_date_range(monday.isoformat(), today.isoformat())

        titles = [t["title"] for t in result]
        # 本周范围内没有待办 → 只有历史未完成的会被累积进来
        assert "旧未完成" in titles
        # "旧已完成" 不应出现（已完成的历史待办不累积）
        assert "旧已完成" not in titles

    def test_no_accumulation_when_end_not_today(self, tmp_db):
        """end_date 不是今天时，不纳入历史未完成待办。"""
        tmp_db.add_todo("历史待办", todo_date="2026-06-01")
        result = tmp_db.get_todos_by_date_range("2026-06-08", "2026-06-13")
        assert result == []
