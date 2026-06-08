"""
TASK-27: 弹窗队列测试
tests/test_popup_queue.py

覆盖：TrayManager 弹窗队列（idle/busy/enqueue/dequeue/overflow）
"""
import pytest
from collections import deque
from unittest.mock import MagicMock, patch

from src.app import TrayManager


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_app():
    return MagicMock()


@pytest.fixture
def tray_mgr(qapp, tmp_config, tmp_db, engine, reminder_engine):
    """创建 TrayManager 实例，不调用 setup() 以免显示系统托盘。"""
    app_mock = MagicMock()
    mgr = TrayManager(app_mock, tmp_config, tmp_db, engine,
                      reminder_engine=reminder_engine)
    return mgr


# ═══════════════════════════════════════════════════════════════════
# Test cases
# ═══════════════════════════════════════════════════════════════════

class TestPopupQueueIdle:
    """空闲状态 → 直接显示。"""

    def test_idle_creates_popup(self, tray_mgr):
        """无活跃弹窗时 _on_reminder_triggered 创建 ReminderPopup。"""
        # 确保弹窗不实际显示
        with patch("src.app.ReminderPopup") as MockPopup:
            mock_popup = MagicMock()
            MockPopup.return_value = mock_popup
            tray_mgr._on_reminder_triggered(1, "测试", "10:00")

            MockPopup.assert_called_once()
            mock_popup.show_and_focus.assert_called_once()
            assert tray_mgr._active_popup is mock_popup

    def test_idle_sets_active_popup(self, tray_mgr):
        """空闲时 _active_popup 被设置。"""
        assert tray_mgr._active_popup is None
        with patch("src.app.ReminderPopup") as MockPopup:
            mock_popup = MagicMock()
            MockPopup.return_value = mock_popup
            tray_mgr._on_reminder_triggered(1, "测试", "10:00")
            assert tray_mgr._active_popup is not None

    def test_idle_queue_empty(self, tray_mgr):
        """空闲时不使用队列。"""
        with patch("src.app.ReminderPopup") as MockPopup:
            MockPopup.return_value = MagicMock()
            tray_mgr._on_reminder_triggered(1, "测试", "10:00")
            assert len(tray_mgr._popup_queue) == 0


class TestPopupQueueBusy:
    """忙碌状态 → 入队。"""

    def test_busy_enqueues(self, tray_mgr):
        """已有活跃弹窗时新提醒入队。"""
        with patch("src.app.ReminderPopup") as MockPopup:
            popup1 = MagicMock()
            popup2 = MagicMock()
            MockPopup.side_effect = [popup1, popup2]

            # First: becomes active
            tray_mgr._on_reminder_triggered(1, "A", "10:00")
            assert tray_mgr._active_popup is popup1

            # Second: enqueued
            tray_mgr._on_reminder_triggered(2, "B", "10:30")
            assert tray_mgr._active_popup is popup1  # still popup1
            assert len(tray_mgr._popup_queue) == 1
            assert tray_mgr._popup_queue[0] is popup2

    def test_busy_does_not_show_second(self, tray_mgr):
        """入队弹窗不立即显示。"""
        with patch("src.app.ReminderPopup") as MockPopup:
            popup1 = MagicMock()
            popup2 = MagicMock()
            MockPopup.side_effect = [popup1, popup2]

            tray_mgr._on_reminder_triggered(1, "A", "10:00")
            tray_mgr._on_reminder_triggered(2, "B", "10:30")

            popup1.show_and_focus.assert_called_once()
            popup2.show_and_focus.assert_not_called()


class TestPopupQueueOverflow:
    """队列满 (maxlen=2) → 替换队尾。"""

    def test_queue_maxlen_enforces_limit(self, tray_mgr):
        """deque(maxlen=2) 自动丢弃最旧元素。"""
        with patch("src.app.ReminderPopup") as MockPopup:
            popups = [MagicMock() for _ in range(5)]
            for p in popups:
                p.isVisible.return_value = False
            MockPopup.side_effect = popups

            # Fill: active + 2 in queue
            tray_mgr._on_reminder_triggered(1, "A", "10:00")  # active
            tray_mgr._on_reminder_triggered(2, "B", "10:30")  # queue[0]
            tray_mgr._on_reminder_triggered(3, "C", "11:00")  # queue[1]
            assert len(tray_mgr._popup_queue) == 2

            # 4th: queue full, maxlen=2 → oldest (B) gets dropped
            tray_mgr._on_reminder_triggered(4, "D", "11:30")
            assert len(tray_mgr._popup_queue) == 2

    def test_queue_overflow_does_not_affect_active(self, tray_mgr):
        """溢出不影响活跃弹窗。"""
        with patch("src.app.ReminderPopup") as MagicMockPopup:
            popups = [MagicMock() for _ in range(5)]
            for p in popups:
                p.isVisible.return_value = False
            MagicMockPopup.side_effect = popups

            tray_mgr._on_reminder_triggered(1, "A", "10:00")
            active = tray_mgr._active_popup
            for i in range(2, 6):
                tray_mgr._on_reminder_triggered(i, f"R{i}", "10:00")

            assert tray_mgr._active_popup is active


class TestPopupQueueDrain:
    """关闭当前弹窗 → 自动出队下一个。"""

    def test_on_popup_closed_shows_next(self, tray_mgr):
        """关闭活跃弹窗后自动显示队列中的下一个。"""
        with patch("src.app.ReminderPopup") as MockPopup:
            p1 = MagicMock()
            p1.isVisible.return_value = False
            p2 = MagicMock()
            p2.isVisible.return_value = False
            MockPopup.side_effect = [p1, p2]

            tray_mgr._on_reminder_triggered(1, "A", "10:00")
            tray_mgr._on_reminder_triggered(2, "B", "10:30")

            # Simulate popup closed
            tray_mgr._on_popup_closed()

            assert tray_mgr._active_popup is p2
            p2.show_and_focus.assert_called_once()

    def test_drain_empties_queue(self, tray_mgr):
        """队列全部弹出后为空。"""
        with patch("src.app.ReminderPopup") as MockPopup:
            popups = [MagicMock() for _ in range(3)]
            for p in popups:
                p.isVisible.return_value = False
            MockPopup.side_effect = popups

            tray_mgr._on_reminder_triggered(1, "A", "10:00")
            tray_mgr._on_reminder_triggered(2, "B", "10:30")
            tray_mgr._on_reminder_triggered(3, "C", "11:00")

            # Close 3 times
            tray_mgr._on_popup_closed()
            tray_mgr._on_popup_closed()
            tray_mgr._on_popup_closed()

            assert tray_mgr._active_popup is None
            assert len(tray_mgr._popup_queue) == 0

    def test_drain_skips_already_visible(self, tray_mgr):
        """跳过已在显示的队内弹窗。"""
        with patch("src.app.ReminderPopup") as MockPopup:
            p1 = MagicMock()
            p1.isVisible.return_value = False
            p2 = MagicMock()
            p2.isVisible.return_value = True  # Already visible
            p3 = MagicMock()
            p3.isVisible.return_value = False
            MockPopup.side_effect = [p1, p2, p3]

            tray_mgr._on_reminder_triggered(1, "A", "10:00")
            tray_mgr._on_reminder_triggered(2, "B", "10:30")
            tray_mgr._on_reminder_triggered(3, "C", "11:00")

            # Close first - p2 skipped (visible), p3 shown
            tray_mgr._on_popup_closed()

            assert tray_mgr._active_popup is p3


class TestPopupQueueSnooze:
    """snooze 回调。"""

    def test_snooze_calls_engine(self, tray_mgr, reminder_engine):
        """snooze 回调调用 reminder_engine.snooze_reminder。"""
        rid = reminder_engine.add_reminder("测试", "10:00")
        tray_mgr._on_reminder_snoozed(rid)
        r = tray_mgr.db.get_reminder(rid)
        # snooze 会把时间 +10min
        assert r["remind_time"] != "10:00"

    def test_snooze_no_engine_does_not_crash(self, tray_mgr):
        """无 reminder_engine 时 snooze 静默。"""
        tray_mgr._reminder_engine = None
        tray_mgr._on_reminder_snoozed(999)  # Should not raise


class TestPopupQueueDismiss:
    """dismiss 回调。"""

    def test_dismiss_does_not_crash(self, tray_mgr):
        """dismiss 回调不崩溃。"""
        tray_mgr._on_reminder_dismissed(1)  # no-op

    def test_dismiss_no_engine_ok(self, tray_mgr):
        tray_mgr._reminder_engine = None
        tray_mgr._on_reminder_dismissed(1)
