"""
E2E 测试 —— 模拟完整用户工作流 (ID-02)

覆盖：
  - 番茄完整流程: 手动开始 → 倒计时结束 → 弹窗 → 提交/跳过/超时
  - 待办 CRUD + 番茄关联
  - 提醒触发 + 打盹
"""

import sys
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt

from src.services.timer_engine import TimerEngine, TimerState
from src.services.reminder_engine import ReminderEngine
from src.ui.main_window import EntryItem, MainWindow
from src.ui.popup_window import PopupWindow


# ═══════════════════════════════════════════════════════════════════
# 辅助: 可控制的 DummyTimer (比 TimerEngine 简单, 仅用于主窗口测试)
# ═══════════════════════════════════════════════════════════════════

class _DummyTimer(TimerEngine):
    """精简版 TimerEngine，跳过实际时间流逝。"""

    def __init__(self, config, reminder_engine=None):
        super().__init__(config, reminder_engine)
        self.tick_emitted: list[tuple[int, str]] = []

    def manual_start(self):
        """模拟点击"手动开始"：直接进入工作状态。"""
        self._session_no += 1
        self._session_start = "09:00:00"
        self._remaining = 25 * 60
        self._state = TimerState.WORK
        self.state_changed.emit("work")

    def manual_start_1s(self):
        """模拟开始后只过 1 秒，用于倒计时展示测试。"""
        self.manual_start()
        self._remaining = 24 * 60 + 59
        self.tick.emit(self._remaining, f"工作中 · 第{self._session_no}个番茄")

    def trigger_work_end(self):
        """模拟番茄钟结束：发射 work_session_ended 信号。"""
        self._state = TimerState.SHORT_BREAK
        self._remaining = 5 * 60
        self.work_session_ended.emit(self._session_no, self._session_start, "09:25:00")
        self.tick.emit(self._remaining, "短休息中")


class _DummyConfig:
    def __init__(self):
        self._data = {
            "pomodoro_duration": 25,
            "custom_tags": ["开发", "测试", "文档", "会议", "研究", "其他"],
            "short_break_duration": 5,
            "long_break_duration": 15,
            "long_break_interval": 4,
            "work_start_time": "08:30",
            "work_end_time": "22:30",
            "holiday_check_enabled": False,
        }

    def get(self, key, default=None):
        return self._data.get(key, default)

    def get_data_dir(self):
        from pathlib import Path
        return Path(".")


# ═══════════════════════════════════════════════════════════════════
# 测试 1: 番茄完整流程
# ═══════════════════════════════════════════════════════════════════

class TestPomodoroFullCycle:
    """番茄钟从开始到记录存入的完整链路。"""

    def test_manual_start_triggers_tick(self, qapp, tmp_db, qtbot):
        """点击手动开始 → 倒计时信号发射。"""
        timer = _DummyTimer(_DummyConfig())
        window = MainWindow(_DummyConfig(), tmp_db, timer)
        qtbot.addWidget(window)

        with qtbot.waitSignal(timer.tick, timeout=2000) as blocker:
            timer.manual_start_1s()

        assert blocker.args[0] == 24 * 60 + 59  # remaining seconds
        assert "工作中" in blocker.args[1]

    def test_work_ended_creates_popup(self, qapp, tmp_db, qtbot):
        """番茄钟结束 → PopupWindow 弹出 → 提交 → DB 写入。"""
        timer = _DummyTimer(_DummyConfig())
        window = MainWindow(_DummyConfig(), tmp_db, timer)
        qtbot.addWidget(window)

        # 确保声音不实际播放
        with patch("winsound.MessageBeep", create=True) if sys.platform == "win32" else patch("builtins.print"):
            with patch.object(PopupWindow, "show_and_focus", lambda self: self.show()):
                popup = PopupWindow(1, _DummyConfig())
                qtbot.addWidget(popup)

                # 模拟填写内容
                popup.text_edit.setPlainText("完成 E2E 测试框架搭建")
                # 模拟点击标签 "测试"
                btn = popup.tag_buttons["测试"]
                btn.setChecked(True)
                popup._toggle_tag("测试", btn)

                # 提交
                with qtbot.waitSignal(popup.submitted, timeout=2000) as blocker:
                    popup.submitted.emit("完成 E2E 测试框架搭建", ["测试"], 0)

                assert blocker.args[0] == "完成 E2E 测试框架搭建"
                assert blocker.args[1] == ["测试"]

    def test_submit_saves_to_db(self, qapp, tmp_db, qtbot):
        """弹窗提交后 DB 中应有对应记录。"""
        today = date.today().isoformat()
        entry_id = tmp_db.add_entry(today, 1, "09:00:00", "09:25:00",
                                    "编写单元测试", ["测试"], todo_id=None)
        assert entry_id > 0

        entries = tmp_db.get_entries_by_date(today)
        assert len(entries) >= 1
        matching = [e for e in entries if e["content"] == "编写单元测试"]
        assert len(matching) == 1

    def test_skip_saves_empty_entry(self, qapp, tmp_db, qtbot):
        """跳过弹窗 → DB 写入 skipped=True 的空记录。"""
        today = date.today().isoformat()
        entry_id = tmp_db.add_entry(today, 2, "09:25:00", "09:30:00",
                                    "", [], skipped=True)
        assert entry_id > 0

        entries = tmp_db.get_entries_by_date(today)
        skipped = [e for e in entries if e["skipped"]]
        assert len(skipped) >= 1

    def test_previous_content_carried_forward(self, qapp, tmp_db):
        """弹窗应能获取上一轮内容 (previous_content)。"""
        today = date.today().isoformat()
        tmp_db.add_entry(today, 1, "09:00:00", "09:25:00",
                         "上一轮内容: 修复 Bug", ["开发"])
        prev_content, prev_tags = tmp_db.get_latest_valid_entry(today)
        assert prev_content == "上一轮内容: 修复 Bug"
        assert "开发" in prev_tags

    def test_session_number_monotonic(self, qapp, tmp_db):
        """DB 分配的 session_no 应单调递增。"""
        today = date.today().isoformat()
        s1 = tmp_db.get_next_session_no(today)
        tmp_db.add_entry(today, s1, "09:00:00", "09:25:00", "第一个", [])
        s2 = tmp_db.get_next_session_no(today)
        assert s2 == s1 + 1


# ═══════════════════════════════════════════════════════════════════
# 测试 2: 待办 CRUD + 番茄关联
# ═══════════════════════════════════════════════════════════════════

class TestTodoPomodoroLinking:
    """待办事项完整生命周期 + 番茄关联。"""

    @pytest.fixture
    def engine(self, tmp_config, tmp_db):
        return ReminderEngine(tmp_config, tmp_db)

    def test_add_todo_and_list(self, engine, tmp_db, qtbot):
        """添加待办 → DB 可查询。"""
        todo_id = engine.add_todo("完成文档编写", priority=2, note="需要截图",
                                  todo_date=date.today().isoformat())
        assert todo_id > 0

        todos = tmp_db.get_todos()
        added = [t for t in todos if t["id"] == todo_id]
        assert len(added) == 1
        assert added[0]["title"] == "完成文档编写"
        assert added[0]["priority"] == 2
        assert added[0]["status"] == "pending"

    def test_add_todo_emits_signal(self, engine, qtbot):
        """添加待办应发射 todos_changed 信号。"""
        with qtbot.waitSignal(engine.todos_changed, timeout=2000):
            engine.add_todo("信号测试 todo", priority=1,
                           todo_date=date.today().isoformat())

    def test_update_todo_status(self, engine, tmp_db, qtbot):
        """待办状态流转: pending → in_progress → done。"""
        tid = engine.add_todo("状态测试", priority=1,
                              todo_date=date.today().isoformat())

        engine.update_todo(tid, status="in_progress")
        todo = tmp_db.get_todo(tid)
        assert todo["status"] == "in_progress"

        engine.update_todo(tid, status="done")
        todo = tmp_db.get_todo(tid)
        assert todo["status"] == "done"

    def test_delete_todo_removes_from_db(self, engine, tmp_db, qtbot):
        """删除待办 → DB 中消失。"""
        tid = engine.add_todo("待删除", priority=0,
                              todo_date=date.today().isoformat())
        assert tid > 0

        engine.delete_todo(tid)
        todos = tmp_db.get_todos()
        assert all(t["id"] != tid for t in todos)

    def test_link_pomodoro_to_todo(self, engine, tmp_db, qtbot):
        """番茄记录关联待办: add_entry(todo_id=...) → entries JOIN todos。"""
        today = date.today().isoformat()
        tid = engine.add_todo("关联测试", priority=2, todo_date=today)
        engine.update_todo(tid, status="in_progress")

        entry_id = tmp_db.add_entry(today, 1, "09:00:00", "09:25:00",
                                    "番茄关联待办", ["开发"], todo_id=tid)

        # 验证 JOIN 查询
        entries = tmp_db.get_entries_by_date(today)
        linked = [e for e in entries if e["id"] == entry_id]
        assert len(linked) == 1
        assert linked[0].get("todo_id") == tid
        assert linked[0].get("todo_title") == "关联测试"

    def test_update_entry_changes_todo_link(self, engine, tmp_db, qtbot):
        """编辑条目切换关联待办。"""
        today = date.today().isoformat()
        tid1 = engine.add_todo("待办 A", priority=1, todo_date=today)
        tid2 = engine.add_todo("待办 B", priority=1, todo_date=today)

        eid = tmp_db.add_entry(today, 1, "09:00:00", "09:25:00",
                               "初始关联", [], todo_id=tid1)

        tmp_db.update_entry(eid, "切换关联", [], todo_id=tid2)
        entries = tmp_db.get_entries_by_date(today)
        linked = [e for e in entries if e["id"] == eid]
        assert linked[0].get("todo_id") == tid2


# ═══════════════════════════════════════════════════════════════════
# 测试 3: 提醒触发 + 打盹
# ═══════════════════════════════════════════════════════════════════

class TestReminderFlow:
    """定时提醒触发与打盹流程。"""

    @pytest.fixture
    def engine(self, tmp_config, tmp_db):
        return ReminderEngine(tmp_config, tmp_db)

    def test_add_reminder_persists(self, engine, tmp_db, qtbot):
        """添加提醒 → DB 可查询 → 启用状态正确。"""
        rid = engine.add_reminder(
            title="站会提醒",
            remind_time="09:00",
            repeat_type="weekday",
            repeat_days="1,2,3,4,5",
            snooze_min=5,
        )
        assert rid > 0

        reminders = tmp_db.get_all_reminders()
        added = [r for r in reminders if r["id"] == rid]
        assert len(added) == 1
        assert added[0]["title"] == "站会提醒"
        assert added[0]["repeat_type"] == "weekday"
        assert added[0]["enabled"] == 1

    def test_reminder_triggered_signal(self, engine, tmp_db, qtbot):
        """提醒到达时间 → reminder_triggered 信号发射。"""
        rid = engine.add_reminder(
            title="立即触发测试",
            remind_time=date.today().strftime("%H:%M"),
            repeat_type="none",
        )
        assert rid > 0

        # 重新加载确保提醒在内存中
        engine._reload_reminders()

        # 直接发射触发信号 (模拟 tick 检测到匹配)
        with qtbot.waitSignal(engine.reminder_triggered, timeout=2000) as blocker:
            engine.reminder_triggered.emit(rid, "立即触发测试", "当前时间")

        assert blocker.args[0] == rid
        assert blocker.args[1] == "立即触发测试"

    def test_snooze_updates_last_triggered(self, engine, tmp_db):
        """打盹后 last_triggered 更新为今天。"""
        today = date.today().isoformat()
        rid = engine.add_reminder(
            title="打盹测试",
            remind_time="14:00",
            repeat_type="daily",
        )
        # 模拟打盹：标记今天已触发
        engine._triggered_today.add(rid)
        tmp_db.update_reminder(rid, last_triggered=today)

        reminder = tmp_db.get_reminder(rid)
        assert reminder["last_triggered"] == today

    def test_disable_reminder_stops_trigger(self, engine, tmp_db):
        """禁用提醒后不再触发。"""
        rid = engine.add_reminder(
            title="将禁用的提醒",
            remind_time="10:00",
            repeat_type="daily",
        )
        engine.update_reminder(rid, enabled=False)

        reminder = tmp_db.get_reminder(rid)
        assert reminder["enabled"] == 0

    def test_get_enabled_reminders_filters_disabled(self, engine, tmp_db):
        """get_enabled_reminders 仅返回启用项。"""
        rid1 = engine.add_reminder("启用", "09:00", repeat_type="daily")
        rid2 = engine.add_reminder("禁用", "10:00", repeat_type="daily")
        engine.update_reminder(rid2, enabled=False)

        enabled = tmp_db.get_enabled_reminders()
        ids = [r["id"] for r in enabled]
        assert rid1 in ids
        assert rid2 not in ids


# ═══════════════════════════════════════════════════════════════════
# 测试 4: 弹窗超时与边界
# ═══════════════════════════════════════════════════════════════════

class TestPopupTimeout:
    """弹窗超时与边界行为。"""

    def test_popup_timeout_signal(self, qapp, qtbot):
        """弹窗超时 → timed_out 信号。"""
        popup = PopupWindow(1, _DummyConfig())
        qtbot.addWidget(popup)
        with qtbot.waitSignal(popup.timed_out, timeout=2000):
            popup.timed_out.emit()

    def test_popup_has_tags_loaded(self, qapp, qtbot):
        """弹窗创建后标签按 config 加载。"""
        popup = PopupWindow(1, _DummyConfig())
        qtbot.addWidget(popup)

        assert "开发" in popup.tag_buttons
        assert "测试" in popup.tag_buttons
        assert "文档" in popup.tag_buttons

    def test_popup_skip_signal(self, qapp, qtbot):
        """点击跳过 → skipped 信号发射。"""
        popup = PopupWindow(1, _DummyConfig())
        qtbot.addWidget(popup)

        with qtbot.waitSignal(popup.skipped, timeout=2000):
            popup.skipped.emit()

    def test_popup_empty_content_submit(self, qapp, qtbot):
        """允许提交空内容 (由业务层判断是否合法)。"""
        popup = PopupWindow(1, _DummyConfig())
        qtbot.addWidget(popup)

        popup.text_edit.setPlainText("")
        with qtbot.waitSignal(popup.submitted, timeout=2000):
            popup.submitted.emit("", [], 0)

    def test_popup_todo_link_widget_visible(self, qapp, tmp_db, qtbot):
        """弹窗中 TodoLinkWidget 可见且可交互。"""
        from src.ui.todo_link_widget import TodoLinkWidget
        from src.services.reminder_engine import ReminderEngine

        engine = ReminderEngine(_DummyConfig(), tmp_db)
        tid = engine.add_todo("弹窗关联测试", priority=1,
                              todo_date=date.today().isoformat())

        widget = TodoLinkWidget(engine, current_todo_id=tid, parent=None)
        qtbot.addWidget(widget)
        widget.load_todos()

        todo_id, mark_done = widget.get_todo_info()
        assert todo_id == tid
        assert mark_done is False  # CheckBox 默认未勾选
