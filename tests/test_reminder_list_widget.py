"""
ReminderListWidget 单元测试

覆盖：初始化、refresh 展示、添加提醒、编辑/删除/切换、日期偏移、重复类型切换。
"""
import pytest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QDate, QTime


@pytest.fixture
def widget(qapp, reminder_engine):
    """创建 ReminderListWidget 实例。"""
    from src.ui.reminder_list_widget import ReminderListWidget
    w = ReminderListWidget(reminder_engine)
    return w


# ═══════════════════════════════════════════════════════════════════
# 初始化与空状态
# ═══════════════════════════════════════════════════════════════════

class TestReminderListInit:
    def test_widget_creates_successfully(self, widget):
        """Widget 创建不抛异常。"""
        assert widget is not None

    def test_empty_state_shows_placeholder(self, widget):
        """无提醒时显示占位提示文本。"""
        from PyQt6.QtWidgets import QLabel
        labels = widget._cards_widget.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert any("暂无提醒" in t for t in texts)

    def test_title_input_exists(self, widget):
        """标题输入框存在且为空。"""
        assert widget._title_input.text() == ""

    def test_repeat_combo_defaults_to_no_repeat(self, widget):
        """重复下拉默认为 "不重复"。"""
        assert widget._repeat_combo.currentIndex() == 0


# ═══════════════════════════════════════════════════════════════════
# 添加提醒
# ═══════════════════════════════════════════════════════════════════

class TestReminderAdd:
    def test_add_empty_title_does_nothing(self, widget, reminder_engine):
        """空标题不添加提醒。"""
        widget._title_input.setText("")
        widget._on_add()
        assert reminder_engine.get_all_reminders() == []

    def test_add_reminder_success(self, widget, reminder_engine):
        """正常输入标题后添加成功。"""
        widget._title_input.setText("喝水提醒")
        widget._add_time.setTime(QTime(14, 30))
        widget._on_add()
        reminders = reminder_engine.get_all_reminders()
        assert len(reminders) == 1
        assert reminders[0]["title"] == "喝水提醒"
        assert reminders[0]["remind_time"] == "14:30"

    def test_add_clears_input_after_success(self, widget):
        """添加成功后输入框被清空。"""
        widget._title_input.setText("站起来活动")
        widget._on_add()
        assert widget._title_input.text() == ""

    def test_add_with_daily_repeat(self, widget, reminder_engine):
        """选择'每天'重复后添加，remind_date 应为 None。"""
        widget._title_input.setText("每日站会")
        widget._repeat_combo.setCurrentIndex(1)  # 每天
        widget._on_add()
        reminders = reminder_engine.get_all_reminders()
        assert len(reminders) == 1
        assert reminders[0]["repeat_type"] == "daily"
        assert reminders[0].get("remind_date") is None

    def test_add_with_weekly_repeat(self, widget, reminder_engine):
        """选择'每周'重复后添加。"""
        widget._title_input.setText("周会")
        widget._repeat_combo.setCurrentIndex(2)  # 每周
        widget._on_add()
        reminders = reminder_engine.get_all_reminders()
        assert reminders[0]["repeat_type"] == "weekly"

    def test_add_with_weekday_repeat(self, widget, reminder_engine):
        """选择'工作日'重复后添加。"""
        widget._title_input.setText("工作日打卡")
        widget._repeat_combo.setCurrentIndex(3)  # 工作日
        widget._on_add()
        reminders = reminder_engine.get_all_reminders()
        assert reminders[0]["repeat_type"] == "weekday"

    def test_add_no_repeat_includes_date(self, widget, reminder_engine):
        """不重复模式下添加应包含 remind_date。"""
        widget._title_input.setText("面试")
        widget._repeat_combo.setCurrentIndex(0)  # 不重复
        widget._add_date.setDate(QDate(2025, 6, 15))
        widget._on_add()
        reminders = reminder_engine.get_all_reminders()
        assert reminders[0]["remind_date"] == "2025-06-15"
        assert reminders[0]["repeat_type"] == "none"


# ═══════════════════════════════════════════════════════════════════
# Refresh 与卡片渲染
# ═══════════════════════════════════════════════════════════════════

class TestReminderRefresh:
    def test_refresh_shows_cards_after_add(self, widget, reminder_engine):
        """添加提醒后 refresh 应生成卡片。"""
        reminder_engine.add_reminder("测试提醒", "09:00",
                                     remind_date="2025-07-01",
                                     repeat_type="none", snooze_min=10)
        widget.refresh()
        from PyQt6.QtWidgets import QFrame
        cards = widget._cards_widget.findChildren(QFrame)
        assert len(cards) >= 1

    def test_refresh_multiple_reminders(self, widget, reminder_engine):
        """多个提醒应生成对应数量的卡片。"""
        for i in range(3):
            reminder_engine.add_reminder(f"提醒{i}", f"0{i+1}:00",
                                         remind_date="2025-07-01",
                                         repeat_type="none", snooze_min=10)
        widget.refresh()
        from PyQt6.QtWidgets import QFrame
        cards = [c for c in widget._cards_widget.findChildren(QFrame)
                 if c.objectName() == "reminderCard"]
        assert len(cards) == 3

    def test_refresh_clears_old_cards(self, widget, reminder_engine):
        """refresh 后旧卡片被清除。"""
        reminder_engine.add_reminder("旧提醒", "08:00",
                                     remind_date="2025-07-01",
                                     repeat_type="none", snooze_min=10)
        widget.refresh()
        # 删除后再 refresh
        reminders = reminder_engine.get_all_reminders()
        reminder_engine.delete_reminder(reminders[0]["id"])
        widget.refresh()
        from PyQt6.QtWidgets import QLabel
        labels = widget._cards_widget.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert any("暂无提醒" in t for t in texts)


# ═══════════════════════════════════════════════════════════════════
# 切换（Toggle）
# ═══════════════════════════════════════════════════════════════════

class TestReminderToggle:
    def test_toggle_disables_reminder(self, widget, reminder_engine):
        """切换提醒应将 enabled 变为 0。"""
        reminder_engine.add_reminder("切换测试", "10:00",
                                     remind_date="2025-07-01",
                                     repeat_type="none", snooze_min=10)
        reminders = reminder_engine.get_all_reminders()
        rid = reminders[0]["id"]
        widget._on_toggle(rid)
        updated = reminder_engine.db.get_reminder(rid)
        assert updated["enabled"] == 0

    def test_toggle_enables_disabled_reminder(self, widget, reminder_engine):
        """已禁用的提醒再次切换应重新启用。"""
        reminder_engine.add_reminder("切换测试2", "11:00",
                                     remind_date="2025-07-01",
                                     repeat_type="none", snooze_min=10)
        reminders = reminder_engine.get_all_reminders()
        rid = reminders[0]["id"]
        # 先禁用
        widget._on_toggle(rid)
        # 再启用
        widget._on_toggle(rid)
        updated = reminder_engine.db.get_reminder(rid)
        assert updated["enabled"] == 1


# ═══════════════════════════════════════════════════════════════════
# 删除（带 QMessageBox mock）
# ═══════════════════════════════════════════════════════════════════

class TestReminderDelete:
    def test_delete_confirmed_removes_reminder(self, widget, reminder_engine):
        """确认删除后提醒被移除。"""
        reminder_engine.add_reminder("删除测试", "12:00",
                                     remind_date="2025-07-01",
                                     repeat_type="none", snooze_min=10)
        reminders = reminder_engine.get_all_reminders()
        rid = reminders[0]["id"]
        with patch("src.ui.reminder_list_widget.QMessageBox.question",
                   return_value=QMessageBox_Yes()):
            widget._on_delete(rid)
        assert reminder_engine.get_all_reminders() == []

    def test_delete_cancelled_keeps_reminder(self, widget, reminder_engine):
        """取消删除后提醒仍然存在。"""
        reminder_engine.add_reminder("不删", "13:00",
                                     remind_date="2025-07-01",
                                     repeat_type="none", snooze_min=10)
        reminders = reminder_engine.get_all_reminders()
        rid = reminders[0]["id"]
        with patch("src.ui.reminder_list_widget.QMessageBox.question",
                   return_value=QMessageBox_No()):
            widget._on_delete(rid)
        assert len(reminder_engine.get_all_reminders()) == 1


# ═══════════════════════════════════════════════════════════════════
# 编辑
# ═══════════════════════════════════════════════════════════════════

class TestReminderEdit:
    def test_edit_updates_title(self, widget, reminder_engine):
        """编辑提醒后标题更新。"""
        reminder_engine.add_reminder("原标题", "14:00",
                                     remind_date="2025-07-01",
                                     repeat_type="none", snooze_min=10)
        reminders = reminder_engine.get_all_reminders()
        rid = reminders[0]["id"]

        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = 1  # QDialog.DialogCode.Accepted
        mock_dlg.get_data.return_value = {
            "title": "新标题",
            "remind_time": "15:00",
            "remind_date": "2025-07-02",
            "repeat_type": "none",
            "snooze_min": 5,
        }
        with patch("src.ui.reminder_list_widget._ReminderEditDialog",
                   return_value=mock_dlg):
            widget._on_edit(rid)
        updated = reminder_engine.db.get_reminder(rid)
        assert updated["title"] == "新标题"
        assert updated["remind_time"] == "15:00"

    def test_edit_cancelled_no_change(self, widget, reminder_engine):
        """取消编辑后提醒不变。"""
        reminder_engine.add_reminder("不改", "16:00",
                                     remind_date="2025-07-01",
                                     repeat_type="none", snooze_min=10)
        reminders = reminder_engine.get_all_reminders()
        rid = reminders[0]["id"]

        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = 0  # Rejected
        with patch("src.ui.reminder_list_widget._ReminderEditDialog",
                   return_value=mock_dlg):
            widget._on_edit(rid)
        unchanged = reminder_engine.db.get_reminder(rid)
        assert unchanged["title"] == "不改"

    def test_edit_nonexistent_reminder_noop(self, widget, reminder_engine):
        """编辑不存在的提醒 id 不抛异常。"""
        widget._on_edit(99999)  # Should not raise


# ═══════════════════════════════════════════════════════════════════
# 日期偏移与重复类型联动
# ═══════════════════════════════════════════════════════════════════

class TestDateShiftAndRepeat:
    def test_shift_date_forward(self, widget):
        """前进一天日期变化。"""
        widget._add_date.setDate(QDate(2025, 7, 1))
        widget._shift_add_date(1)
        assert widget._add_date.date() == QDate(2025, 7, 2)

    def test_shift_date_backward(self, widget):
        """后退一天日期变化。"""
        widget._add_date.setDate(QDate(2025, 7, 3))
        widget._shift_add_date(-1)
        assert widget._add_date.date() == QDate(2025, 7, 2)

    def test_repeat_change_disables_date(self, widget):
        """切换为'每天'后日期控件被禁用。"""
        widget._on_add_repeat_changed(1)  # 每天
        assert not widget._add_date.isEnabled()
        assert not widget._date_prev.isEnabled()
        assert not widget._date_next.isEnabled()

    def test_repeat_change_back_enables_date(self, widget):
        """切回'不重复'后日期控件恢复启用。"""
        widget._on_add_repeat_changed(1)  # 每天 → 禁用
        widget._on_add_repeat_changed(0)  # 不重复 → 启用
        assert widget._add_date.isEnabled()
        assert widget._date_prev.isEnabled()
        assert widget._date_next.isEnabled()


# ═══════════════════════════════════════════════════════════════════
# _ReminderEditDialog 单元测试
# ═══════════════════════════════════════════════════════════════════

class TestReminderEditDialog:
    def test_dialog_creation_defaults(self, qapp):
        """默认参数创建对话框。"""
        from src.ui.reminder_list_widget import _ReminderEditDialog
        dlg = _ReminderEditDialog()
        data = dlg.get_data()
        assert data["title"] == ""
        assert data["repeat_type"] == "none"
        assert data["snooze_min"] == 10
        assert data["remind_date"] is not None  # 当前日期

    def test_dialog_with_title_and_time(self, qapp):
        """传入标题和时间后回读正确。"""
        from src.ui.reminder_list_widget import _ReminderEditDialog
        dlg = _ReminderEditDialog(title="会议", remind_time="09:30",
                                   remind_date="2025-08-01")
        data = dlg.get_data()
        assert data["title"] == "会议"
        assert data["remind_time"] == "09:30"
        assert data["remind_date"] == "2025-08-01"

    def test_dialog_daily_repeat_no_date(self, qapp):
        """每天重复时 remind_date 为 None。"""
        from src.ui.reminder_list_widget import _ReminderEditDialog
        dlg = _ReminderEditDialog(repeat_type="daily")
        data = dlg.get_data()
        assert data["repeat_type"] == "daily"
        assert data["remind_date"] is None

    def test_dialog_date_hidden_for_repeat(self, qapp):
        """重复模式下日期控件不可见。"""
        from src.ui.reminder_list_widget import _ReminderEditDialog
        dlg = _ReminderEditDialog(repeat_type="weekly")
        assert not dlg.date_edit.isVisible()
        assert not dlg.date_label.isVisible()

    def test_dialog_snooze_value(self, qapp):
        """延后分钟值正确传入。"""
        from src.ui.reminder_list_widget import _ReminderEditDialog
        dlg = _ReminderEditDialog(snooze_min=30)
        data = dlg.get_data()
        assert data["snooze_min"] == 30


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def QMessageBox_Yes():
    from PyQt6.QtWidgets import QMessageBox
    return QMessageBox.StandardButton.Yes


def QMessageBox_No():
    from PyQt6.QtWidgets import QMessageBox
    return QMessageBox.StandardButton.No
