import sys

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut, QTextCursor
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.services.logger import get_logger

logger = get_logger(__name__)


class PopupWindow(QDialog):
    submitted = pyqtSignal(str, list, int)   # content, tags, todo_id (0=none)
    skipped = pyqtSignal()
    timed_out = pyqtSignal()

    def __init__(self, session_no: int, config, previous_content: str = "",
                 previous_tags: list[str] | None = None,
                 parent=None, reminder_engine=None):
        super().__init__(parent)
        self.session_no = session_no
        self.config = config
        self._reminder_engine = reminder_engine
        self.previous_content = (previous_content or "").strip()
        self.previous_tags = previous_tags or []
        self.selected_tags: list[str] = []
        self.timeout_seconds = max(10, int(self.config.get("popup_timeout_seconds", 180)))
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._on_timeout)
        self._setup_window()
        self._setup_ui()

    # ------------------------------------------------------------------
    # Window flags
    # ------------------------------------------------------------------

    def _setup_window(self):
        self.setWindowTitle(f"POMATO · 第{self.session_no}个番茄钟完成")
        # Dialog → Window: 避免 Linux 下输入法框架 (fcitx/ibus) 忽略弹窗
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.setMinimumWidth(440)
        self.setModal(False)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 16)

        # ── header ─────────────────────────────────────────────────────
        header = QLabel(f"🍅 第 {self.session_no} 个番茄钟完成！")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #d32f2f;")
        layout.addWidget(header)

        prompt = QLabel("过去25分钟，你做了什么？")
        prompt.setStyleSheet("font-size: 13px; color: #555;")
        layout.addWidget(prompt)

        # ── US-01: 上下文提示 ───────────────────────────────────
        if self.previous_content:
            truncated = self.previous_content[:50] + ("…" if len(self.previous_content) > 50 else "")
            context_label = QLabel(f"上一轮：{truncated}")
            context_label.setStyleSheet("font-size: 11px; color: #999; background: #f5f5f5;"
                                        " border-radius: 4px; padding: 4px 8px;")
            context_label.setWordWrap(True)
            layout.addWidget(context_label)
        else:
            context_label = QLabel("今天第一个番茄钟 🍅")
            context_label.setStyleSheet("font-size: 11px; color: #bbb; padding: 2px 4px;")
            layout.addWidget(context_label)

        # ── text input ─────────────────────────────────────────────────
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "简洁描述工作内容，例如：完成了登录模块的代码审查，修复了3个bug…"
        )
        self.text_edit.setMinimumHeight(90)
        self.text_edit.setMaximumHeight(120)
        self.text_edit.setStyleSheet(
            """
            QTextEdit {
                border: 1.5px solid #ddd;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                background: #fafafa;
            }
            QTextEdit:focus {
                border-color: #ef5350;
                background: white;
            }
            """
        )
        layout.addWidget(self.text_edit)

        # ── tags ───────────────────────────────────────────────────────
        tag_label = QLabel("标签（可多选）：")
        tag_label.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(tag_label)

        tags_widget = QWidget()
        tags_layout = QHBoxLayout(tags_widget)
        tags_layout.setContentsMargins(0, 0, 0, 0)
        tags_layout.setSpacing(6)

        self.tag_buttons: dict[str, QPushButton] = {}
        for tag in self.config.get("custom_tags", ["开发", "测试", "文档", "会议", "研究", "其他"]):
            btn = QPushButton(tag)
            btn.setCheckable(True)
            btn.setStyleSheet(self._tag_style(False))
            btn.clicked.connect(lambda _checked, t=tag, b=btn: self._toggle_tag(t, b))
            tags_layout.addWidget(btn)
            self.tag_buttons[tag] = btn
        self._tag_list = list(self.tag_buttons.keys())  # US-03: shortcut index → tag name
        tags_layout.addStretch()
        layout.addWidget(tags_widget)

        # ---- 关联待办 (CD-01: extracted TodoLinkWidget) ----
        from src.ui.todo_link_widget import TodoLinkWidget
        self._todo_link = TodoLinkWidget(self._reminder_engine, parent=self)
        layout.addWidget(self._todo_link)

        # ── separator ──────────────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #eee;")
        layout.addWidget(line)

        # ── action buttons ─────────────────────────────────────────────
        btn_layout = QHBoxLayout()

        skip_btn = QPushButton("跳过本轮")
        skip_btn.setStyleSheet(
            """
            QPushButton {
                color: #888; border: 1px solid #ddd;
                border-radius: 5px; padding: 8px 16px;
                font-size: 13px; background: white;
            }
            QPushButton:hover { background: #f5f5f5; }
            """
        )
        skip_btn.clicked.connect(self._on_skip)

        repeat_btn = QPushButton("重复上一条")
        repeat_btn.setEnabled(bool(self.previous_content) or bool(self.previous_tags))
        repeat_btn.setStyleSheet(
            """
            QPushButton {
                color: #666; border: 1px solid #ddd;
                border-radius: 5px; padding: 8px 14px;
                font-size: 13px; background: white;
            }
            QPushButton:hover { background: #f5f5f5; }
            QPushButton:disabled { color:#bbb; border-color:#eee; }
            """
        )
        repeat_btn.clicked.connect(self._on_repeat_last)

        hint = QLabel("Ctrl+Enter 提交")
        hint.setStyleSheet("color: #bbb; font-size: 11px;")

        submit_btn = QPushButton("✓  提交")
        submit_btn.setDefault(True)
        submit_btn.setStyleSheet(
            """
            QPushButton {
                background: #ef5350; color: white;
                border: none; border-radius: 5px;
                padding: 8px 24px; font-size: 13px; font-weight: bold;
            }
            QPushButton:hover   { background: #e53935; }
            QPushButton:pressed { background: #c62828; }
            """
        )
        submit_btn.clicked.connect(self._on_submit)

        btn_layout.addWidget(skip_btn)
        btn_layout.addWidget(repeat_btn)
        btn_layout.addWidget(hint)
        btn_layout.addStretch()
        btn_layout.addWidget(submit_btn)
        layout.addLayout(btn_layout)

        # Ctrl+Enter shortcut
        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        shortcut.activated.connect(self._on_submit)

        # US-03: 额外快捷键
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_submit)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self._on_skip)
        # Ctrl+1~9 切换标签
        for i in range(1, 10):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self).activated.connect(
                self._make_toggle_handler(i)
            )

        # US-02: 上一轮标签自动预选
        self._apply_tag_recommendations()

        self.text_edit.setFocus()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tag_style(selected: bool) -> str:
        if selected:
            return (
                "QPushButton {"
                "  background:#ef5350; color:white;"
                "  border:1.5px solid #ef5350; border-radius:12px;"
                "  padding:3px 10px; font-size:12px;"
                "}"
            )
        return (
            "QPushButton {"
            "  background:white; color:#555;"
            "  border:1.5px solid #ddd; border-radius:12px;"
            "  padding:3px 10px; font-size:12px;"
            "}"
            "QPushButton:hover { border-color:#ef5350; color:#ef5350; }"
        )

    def _toggle_tag(self, tag: str, btn: QPushButton):
        if tag in self.selected_tags:
            self.selected_tags.remove(tag)
            btn.setStyleSheet(self._tag_style(False))
        else:
            self.selected_tags.append(tag)
            btn.setStyleSheet(self._tag_style(True))

    def _on_submit(self):
        self._timeout_timer.stop()
        content = self.text_edit.toPlainText().strip()
        if not content:
            self.text_edit.setStyleSheet(
                self.text_edit.styleSheet() + "border-color: #ef5350;"
            )
            self.text_edit.setFocus()
            return
        todo_id, mark_done = self._todo_link.get_todo_info()
        if todo_id and mark_done and self._reminder_engine:
            self._reminder_engine.update_todo(todo_id, status="done")
        logger.info("Popup submitted: session=%d, tags=%s, todo_id=%d", self.session_no, self.selected_tags, todo_id)
        self.submitted.emit(content, list(self.selected_tags), todo_id)
        self.accept()

    def _on_skip(self):
        self._timeout_timer.stop()
        logger.info("Popup skipped: session=%d", self.session_no)
        self.skipped.emit()
        self.reject()

    def _on_timeout(self):
        if not self.isVisible():
            return
        logger.info("Popup timed out: session=%d", self.session_no)
        self.timed_out.emit()
        self.reject()

    def _on_repeat_last(self):
        if self.previous_content:
            self.text_edit.setPlainText(self.previous_content)
            self.text_edit.setFocus()
            self.text_edit.moveCursor(QTextCursor.MoveOperation.End)
        if self.previous_tags:
            for tag in self.previous_tags:
                if tag in self.tag_buttons:
                    btn = self.tag_buttons[tag]
                    if tag not in self.selected_tags:
                        self.selected_tags.append(tag)
                    btn.setStyleSheet(self._tag_style(True))

    # ── US-03 快捷键辅助 ────────────────────────────────────

    def _make_toggle_handler(self, index: int):
        """Return a callable that toggles the tag at 1-based `index`."""
        def handler():
            idx = index - 1
            if 0 <= idx < len(self._tag_list):
                tag = self._tag_list[idx]
                btn = self.tag_buttons[tag]
                self._toggle_tag(tag, btn)
        return handler

    # ── US-02 标签预选 ──────────────────────────────────────

    def _apply_tag_recommendations(self):
        """Auto-select tags from the previous valid entry."""
        for tag in self.previous_tags:
            if tag in self.tag_buttons and tag not in self.selected_tags:
                self.selected_tags.append(tag)
                self.tag_buttons[tag].setStyleSheet(self._tag_style(True))
        if self.previous_tags:
            logger.debug("Auto-selected previous tags: %s", self.previous_tags)

    # ------------------------------------------------------------------
    # Public: bring to foreground
    # ------------------------------------------------------------------

    def show_and_focus(self):
        self._timeout_timer.start(self.timeout_seconds * 1000)
        self.show()
        self.raise_()
        self.activateWindow()
        self._force_foreground()
        self.text_edit.setFocus()

    def _force_foreground(self):
        """Best-effort foreground window (Windows only)."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            # Simulate a key event so SetForegroundWindow is allowed
            ctypes.windll.user32.keybd_event(0, 0, 0, 0)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            logger.debug("ctypes foreground window failed", exc_info=True)
