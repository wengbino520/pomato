"""
C4 弹窗体验优化测试
tests/test_popup_window.py

覆盖：
  US-01 — 上下文标签（有/无 previous_content）
  US-02 — 上一轮标签自动预选
  US-03 — Ctrl+1~9 / Ctrl+D / Ctrl+S 快捷键
  US-04 — BreakReminderWindow 淡入/淡出/点击关闭
"""

from unittest.mock import MagicMock


from src.ui.popup_window import PopupWindow
from src.ui.break_reminder import BreakReminderWindow
from src.ui.tag_selector_widget import TagSelectorWidget


# ═══════════════════════════════════════════════════════════════════
# TagSelectorWidget 组件测试
# ═══════════════════════════════════════════════════════════════════

class TestTagSelectorWidget:
    """TagSelectorWidget 多选按钮组基础功能。"""

    def test_create_empty(self, qapp):
        ts = TagSelectorWidget(["开发", "测试", "文档"])
        assert ts.selected_tags() == []

    def test_preselect_tags(self, qapp):
        ts = TagSelectorWidget(["开发", "测试", "文档"], selected=["开发", "文档"])
        assert ts.selected_tags() == ["开发", "文档"]

    def test_click_toggles(self, qapp):
        ts = TagSelectorWidget(["开发", "测试"])
        ts.tag_buttons["开发"].click()
        assert "开发" in ts.selected_tags()
        ts.tag_buttons["开发"].click()
        assert "开发" not in ts.selected_tags()

    def test_multi_select(self, qapp):
        ts = TagSelectorWidget(["开发", "测试", "文档"])
        ts.tag_buttons["开发"].click()
        ts.tag_buttons["文档"].click()
        assert ts.selected_tags() == ["开发", "文档"]

    def test_select_tags_ignores_unknown(self, qapp):
        ts = TagSelectorWidget(["开发", "测试"], selected=["不存在", "开发"])
        assert ts.selected_tags() == ["开发"]

    def test_tag_list_ordered(self, qapp):
        ts = TagSelectorWidget(["A", "B", "C"])
        assert ts.tag_list == ["A", "B", "C"]


# ═══════════════════════════════════════════════════════════════════
# PopupWindow US-01 — 上下文标签
# ═══════════════════════════════════════════════════════════════════

class TestPopupContextLabel:
    """US-01: 上一轮上下文提示。"""

    def test_context_label_shows_previous_content(self, qapp, tmp_config):
        """有 previous_content 时显示截断的上下文。"""
        pw = PopupWindow(2, tmp_config, previous_content="完成了登录模块代码审查修复了3个bug")
        pw.show()  # must show for findChild to work

        from PyQt6.QtWidgets import QLabel
        labels = pw.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert any("上一轮" in t for t in texts)
        pw.close()

    def test_context_label_empty_shows_first_pomodoro(self, qapp, tmp_config):
        """无 previous_content 时显示「今天第一个番茄钟」。"""
        pw = PopupWindow(1, tmp_config, previous_content="")
        pw.show()

        from PyQt6.QtWidgets import QLabel
        labels = pw.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert any("第一个番茄钟" in t for t in texts)
        pw.close()

    def test_context_label_long_content_truncated(self, qapp, tmp_config):
        """超过 50 字的内容被截断带省略号。"""
        long_text = "A" * 80
        pw = PopupWindow(3, tmp_config, previous_content=long_text)
        pw.show()

        from PyQt6.QtWidgets import QLabel
        labels = pw.findChildren(QLabel)
        context_texts = [lbl.text() for lbl in labels if "上一轮" in lbl.text()]
        assert len(context_texts) == 1
        assert "…" in context_texts[0]
        assert len(context_texts[0]) < 60  # truncated
        pw.close()


# ═══════════════════════════════════════════════════════════════════
# PopupWindow US-02 — 标签自动预选
# ═══════════════════════════════════════════════════════════════════

class TestPopupTagPreselection:
    """US-02: 上一轮标签自动预选。"""

    def test_previous_tags_auto_selected(self, qapp, tmp_config):
        """previous_tags 中的标签自动选中。"""
        pw = PopupWindow(2, tmp_config, previous_tags=["开发", "文档"])
        pw.show()

        assert "开发" in pw._tag_selector.selected_tags()
        assert "文档" in pw._tag_selector.selected_tags()
        assert "测试" not in pw._tag_selector.selected_tags()
        pw.close()

    def test_empty_previous_tags_no_selection(self, qapp, tmp_config):
        """无 previous_tags 时无预选。"""
        pw = PopupWindow(1, tmp_config, previous_tags=[])
        pw.show()

        assert pw._tag_selector.selected_tags() == []
        pw.close()

    def test_previous_tags_none_no_selection(self, qapp, tmp_config):
        """previous_tags=None 时无预选。"""
        pw = PopupWindow(1, tmp_config, previous_tags=None)
        pw.show()

        assert pw._tag_selector.selected_tags() == []
        pw.close()

    def test_unknown_tags_ignored(self, qapp, tmp_config):
        """不存在于 config 标签列表中的标签被安全忽略。"""
        pw = PopupWindow(2, tmp_config, previous_tags=["不存在的标签", "开发"])
        pw.show()

        assert "开发" in pw._tag_selector.selected_tags()
        assert "不存在的标签" not in pw._tag_selector.selected_tags()
        pw.close()

    def test_multi_tag_selection_via_click(self, qapp, tmp_config):
        """C4 fix: 点击多个标签按钮，全部保持选中状态。"""
        pw = PopupWindow(1, tmp_config)
        pw.show()

        # Click first two tags
        ts = pw._tag_selector
        first_tag = ts.tag_list[0]
        second_tag = ts.tag_list[1]
        ts.tag_buttons[first_tag].click()
        ts.tag_buttons[second_tag].click()

        tags = ts.selected_tags()
        assert first_tag in tags
        assert second_tag in tags
        assert len(tags) == 2
        pw.close()

    def test_multi_tag_toggle_off(self, qapp, tmp_config):
        """C4 fix: 再次点击已选中标签可取消选中，不影响其他标签。"""
        pw = PopupWindow(1, tmp_config)
        pw.show()

        ts = pw._tag_selector
        first_tag = ts.tag_list[0]
        second_tag = ts.tag_list[1]
        ts.tag_buttons[first_tag].click()
        ts.tag_buttons[second_tag].click()
        ts.tag_buttons[first_tag].click()

        tags = ts.selected_tags()
        assert first_tag not in tags
        assert second_tag in tags
        assert len(tags) == 1
        pw.close()


# ═══════════════════════════════════════════════════════════════════
# PopupWindow US-03 — 键盘快捷键
# ═══════════════════════════════════════════════════════════════════

class TestPopupKeyboardShortcuts:
    """US-03: Ctrl+1~9 / Ctrl+D / Ctrl+S。"""

    def test_ctrl_d_triggers_skip(self, qapp, tmp_config):
        """Ctrl+D 触发跳过。"""
        pw = PopupWindow(1, tmp_config)
        pw.show()

        mock = MagicMock()
        pw.skipped.connect(mock)
        from PyQt6.QtGui import QShortcut
        # Find and trigger the Ctrl+D shortcut
        for child in pw.findChildren(QShortcut):
            if child.key().toString() == "Ctrl+D":
                child.activated.emit()
                break
        mock.assert_called_once()
        pw.close()

    def test_ctrl_s_triggers_submit_when_has_content(self, qapp, tmp_config):
        """Ctrl+S 触发提交（需有内容）。"""
        pw = PopupWindow(1, tmp_config)
        pw.text_edit.setPlainText("测试内容")
        pw.show()

        mock = MagicMock()
        pw.submitted.connect(mock)

        from PyQt6.QtGui import QShortcut
        for child in pw.findChildren(QShortcut):
            if child.key().toString() == "Ctrl+S":
                child.activated.emit()
                break
        mock.assert_called_once()
        pw.close()

    def test_ctrl_1_toggles_first_tag(self, qapp, tmp_config):
        """Ctrl+1 切换第一个标签。"""
        pw = PopupWindow(1, tmp_config)
        pw.show()

        ts = pw._tag_selector
        first_tag = ts.tag_list[0]
        assert first_tag not in ts.selected_tags()

        # Trigger Ctrl+1
        from PyQt6.QtGui import QShortcut
        for child in pw.findChildren(QShortcut):
            if child.key().toString() == "Ctrl+1":
                child.activated.emit()
                break

        assert first_tag in ts.selected_tags()
        pw.close()

    def test_ctrl_9_on_fewer_tags_is_safe(self, qapp, tmp_config):
        """标签不足 9 个时 Ctrl+9 不崩溃。"""
        pw = PopupWindow(1, tmp_config)
        pw.show()

        from PyQt6.QtGui import QShortcut
        for child in pw.findChildren(QShortcut):
            if child.key().toString() == "Ctrl+9":
                child.activated.emit()  # should not raise
                break
        pw.close()

    def test_ctrl_enter_submits(self, qapp, tmp_config):
        """Ctrl+Enter 提交。"""
        pw = PopupWindow(1, tmp_config)
        pw.text_edit.setPlainText("内容")
        pw.show()

        mock = MagicMock()
        pw.submitted.connect(mock)

        from PyQt6.QtGui import QShortcut
        for child in pw.findChildren(QShortcut):
            if child.key().toString() == "Ctrl+Return":
                child.activated.emit()
                break
        mock.assert_called_once()
        pw.close()


# ═══════════════════════════════════════════════════════════════════
# BreakReminderWindow US-04 — 淡入提醒窗
# ═══════════════════════════════════════════════════════════════════

class TestBreakReminder:
    """US-04: 休息结束淡入提醒窗。"""

    def test_creates_without_crash(self, qapp):
        """创建 BreakReminderWindow 不崩溃。"""
        brw = BreakReminderWindow()
        assert brw is not None
        # Default opacity is 1.0 until show_with_fade_in() sets it to 0.0
        assert isinstance(brw.windowOpacity(), float)

    def test_show_with_fade_in(self, qapp):
        """show_with_fade_in 显示窗口并启动动画。"""
        brw = BreakReminderWindow()
        brw.show_with_fade_in()

        assert brw.isVisible()
        assert brw._auto_close_timer.isActive()
        brw.close()
        brw.deleteLater()

    def test_click_triggers_fade_out(self, qapp):
        """点击窗口触发淡出。"""
        brw = BreakReminderWindow()
        brw.show_with_fade_in()

        # Simulate click
        brw.mousePressEvent(MagicMock())

        # Timer should be stopped, fade-out should be in progress
        assert not brw._auto_close_timer.isActive()
        assert brw._fade_out_anim is not None
        brw.close()
        brw.deleteLater()

    def test_double_fade_out_is_safe(self, qapp):
        """重复调用 _start_fade_out 不会创建第二个动画。"""
        brw = BreakReminderWindow()
        brw.show_with_fade_in()

        brw._start_fade_out()
        first_anim = brw._fade_out_anim
        brw._start_fade_out()  # should be no-op
        assert brw._fade_out_anim is first_anim
        brw.close()
        brw.deleteLater()

    def test_cleanup_before_new_window(self, qapp):
        """旧窗 close/deleteLater 后再创建新窗不崩溃。"""
        brw1 = BreakReminderWindow()
        brw1.show_with_fade_in()
        brw1.close()
        brw1.deleteLater()

        brw2 = BreakReminderWindow()
        brw2.show_with_fade_in()
        assert brw2.isVisible()
        brw2.close()
        brw2.deleteLater()
