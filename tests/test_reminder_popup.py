"""
TASK-28: ReminderPopup 测试
tests/test_reminder_popup.py

覆盖：弹窗创建/显示/按钮/信号/快捷键/超时
"""
import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut

from src.reminder_popup import ReminderPopup


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def find_button(popup, text: str):
    """查找弹窗中指定文字的 QPushButton。"""
    from PyQt6.QtWidgets import QPushButton
    for btn in popup.findChildren(QPushButton):
        if text in (btn.text() or ""):
            return btn
    return None


def find_shortcut(popup, key):
    """查找匹配快捷键的 QShortcut。"""
    for sc in popup.findChildren(QShortcut):
        if sc.key().toString() == QKeySequence(key).toString():
            return sc
    return None


# ═══════════════════════════════════════════════════════════════════
# TestReminderPopupCreation
# ═══════════════════════════════════════════════════════════════════

class TestReminderPopupCreation:
    """弹窗创建 & 显示。"""

    def test_create_popup(self, qapp):
        popup = ReminderPopup(1, "测试提醒", "14:30")
        assert popup._reminder_id == 1
        assert popup._title == "测试提醒"
        assert popup._remind_time == "14:30"
        assert not popup.isVisible()
        popup.deleteLater()

    def test_set_timeout(self, qapp):
        popup = ReminderPopup(1, "测试", "10:00")
        popup.set_timeout(60)
        assert popup._timeout_seconds == 60
        popup.set_timeout(10)  # below minimum → clamp to 30
        assert popup._timeout_seconds == 30
        popup.deleteLater()

    def test_window_title(self, qapp):
        popup = ReminderPopup(1, "标题", "12:00")
        assert "提醒" in popup.windowTitle()
        popup.deleteLater()

    def test_window_flags(self, qapp):
        popup = ReminderPopup(1, "X", "12:00")
        flags = popup.windowFlags()
        assert flags & Qt.WindowType.WindowStaysOnTopHint
        popup.deleteLater()

    def test_show_and_focus(self, qapp):
        """show_and_focus 显示并启动超时计时器（QTimer 会被启动）。"""
        popup = ReminderPopup(1, "测试", "10:00")
        popup.set_timeout(120)
        try:
            popup.show_and_focus()
            assert popup.isVisible()
            assert popup._timeout_timer.isActive()
        finally:
            popup.hide()
            popup.deleteLater()


# ═══════════════════════════════════════════════════════════════════
# TestReminderPopupButtons
# ═══════════════════════════════════════════════════════════════════

class TestReminderPopupDismiss:
    """知道了按钮 → dismissed 信号。"""

    def test_dismiss_button_exists(self, qapp):
        popup = ReminderPopup(1, "X", "12:00")
        btn = find_button(popup, "知道了")
        assert btn is not None
        popup.deleteLater()

    def test_dismiss_emits_signal(self, qapp):
        popup = ReminderPopup(1, "测试", "12:00")
        signals = []
        popup.dismissed.connect(lambda rid: signals.append(rid))
        btn = find_button(popup, "知道了")
        btn.click()
        assert signals == [1]
        popup.deleteLater()

    def test_dismiss_calls_callback(self, qapp):
        called = []
        popup = ReminderPopup(1, "测试", "12:00",
                              on_dismiss=lambda rid: called.append(rid))
        btn = find_button(popup, "知道了")
        btn.click()
        assert called == [1]
        popup.deleteLater()

    def test_dismiss_stops_timer(self, qapp):
        popup = ReminderPopup(1, "X", "12:00")
        popup.show_and_focus()
        assert popup._timeout_timer.isActive()
        btn = find_button(popup, "知道了")
        btn.click()
        assert not popup._timeout_timer.isActive()
        popup.hide()
        popup.deleteLater()


class TestReminderPopupSnooze:
    """延后按钮 → snoozed 信号。"""

    def test_snooze_button_exists(self, qapp):
        popup = ReminderPopup(1, "X", "12:00")
        btn = find_button(popup, "延后")
        assert btn is not None
        popup.deleteLater()

    def test_snooze_emits_signal(self, qapp):
        popup = ReminderPopup(1, "测试", "12:00")
        signals = []
        popup.snoozed.connect(lambda rid: signals.append(rid))
        btn = find_button(popup, "延后")
        btn.click()
        assert signals == [1]
        popup.deleteLater()

    def test_snooze_calls_callback(self, qapp):
        called = []
        popup = ReminderPopup(1, "测试", "12:00",
                              on_snooze=lambda rid: called.append(rid))
        btn = find_button(popup, "延后")
        btn.click()
        assert called == [1]
        popup.deleteLater()

    def test_snooze_stops_timer(self, qapp):
        popup = ReminderPopup(1, "X", "12:00")
        popup.show_and_focus()
        assert popup._timeout_timer.isActive()
        btn = find_button(popup, "延后")
        btn.click()
        assert not popup._timeout_timer.isActive()
        popup.hide()
        popup.deleteLater()


# ═══════════════════════════════════════════════════════════════════
# TestReminderPopupShortcuts
# ═══════════════════════════════════════════════════════════════════

class TestReminderPopupShortcuts:
    """快捷键测试。"""

    def test_esc_shortcut_exists(self, qapp):
        popup = ReminderPopup(1, "X", "12:00")
        found = any(
            sc.key().toString() == "Esc"
            for sc in popup.findChildren(QShortcut)
        )
        assert found
        popup.deleteLater()

    def test_esc_triggers_dismiss(self, qapp):
        popup = ReminderPopup(1, "测试", "12:00")
        signals = []
        popup.dismissed.connect(lambda rid: signals.append(rid))
        # Find Esc shortcut and activate
        for sc in popup.findChildren(QShortcut):
            if sc.key().toString() == "Esc":
                sc.activated.emit()
                break
        assert signals == [1]
        popup.deleteLater()

    def test_ctrl_s_shortcut_exists(self, qapp):
        popup = ReminderPopup(1, "X", "12:00")
        found = any(
            sc.key().toString() == "Ctrl+S"
            for sc in popup.findChildren(QShortcut)
        )
        assert found
        popup.deleteLater()

    def test_ctrl_s_triggers_snooze(self, qapp):
        popup = ReminderPopup(1, "测试", "12:00")
        signals = []
        popup.snoozed.connect(lambda rid: signals.append(rid))
        for sc in popup.findChildren(QShortcut):
            if sc.key().toString() == "Ctrl+S":
                sc.activated.emit()
                break
        assert signals == [1]
        popup.deleteLater()


# ═══════════════════════════════════════════════════════════════════
# TestReminderPopupTimeout
# ═══════════════════════════════════════════════════════════════════

class TestReminderPopupTimeout:
    """超时自动关闭。"""

    def test_timeout_emits_dismissed(self, qapp):
        popup = ReminderPopup(1, "测试", "12:00")
        popup.set_timeout(30)  # minimum
        signals = []
        popup.dismissed.connect(lambda rid: signals.append(rid))
        try:
            popup.show_and_focus()
            # Fire the timer directly
            popup._on_timeout()
            assert signals == [1]
        finally:
            popup.hide()
            popup.deleteLater()

    def test_timeout_when_not_visible_noop(self, qapp):
        """弹窗不可见时 timeout 不触发 dismiss。"""
        popup = ReminderPopup(1, "X", "12:00")
        signals = []
        popup.dismissed.connect(lambda rid: signals.append(rid))
        # Don't show - call timeout directly
        popup._on_timeout()
        assert signals == []  # No dismiss because not visible
        popup.deleteLater()
