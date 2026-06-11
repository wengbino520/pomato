import sys

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtGui import QTextCursor
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

from PyQt6.QtCore import pyqtSignal


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
        self._selected_todo_id = 0
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
        tags_layout.addStretch()
        layout.addWidget(tags_widget)

        # ---- TASK-21: 关联待办 ----
        from PyQt6.QtWidgets import QComboBox
        from datetime import date
        self._todo_row = QWidget()
        todo_row_layout = QHBoxLayout(self._todo_row)
        todo_row_layout.setContentsMargins(0, 0, 0, 0)
        todo_row_layout.setSpacing(8)

        todo_label = QLabel("关联待办：")
        todo_label.setStyleSheet("font-size:12px; color:#666;")
        self._todo_combo = QComboBox()
        self._todo_combo.addItem("（不关联）", 0)
        self._todo_combo.setStyleSheet(
            "QComboBox { border:1px solid #ddd; border-radius:4px; "
            "padding:4px 8px; font-size:12px; }"
        )
        self._todo_done_cb = QCheckBox("标记完成")
        self._todo_done_cb.setStyleSheet("font-size:12px; color:#666;")

        todo_row_layout.addWidget(todo_label)
        todo_row_layout.addWidget(self._todo_combo, 1)
        todo_row_layout.addWidget(self._todo_done_cb)
        layout.addWidget(self._todo_row)

        # Load todos if engine available
        if self._reminder_engine:
            today_str = date.today().isoformat()
            todos = self._reminder_engine.get_todos(
                date_str=today_str, include_done=False
            )
            for t in todos:
                self._todo_combo.addItem(t["title"], t["id"])
        else:
            self._todo_row.setVisible(False)

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
        todo_id = self._todo_combo.currentData() or 0
        if todo_id and self._todo_done_cb.isChecked() and self._reminder_engine:
            self._reminder_engine.update_todo(todo_id, status="done")
        self.submitted.emit(content, list(self.selected_tags), todo_id)
        self.accept()

    def _on_skip(self):
        self._timeout_timer.stop()
        self.skipped.emit()
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

    def _on_timeout(self):
        if not self.isVisible():
            return
        self.timed_out.emit()
        self.reject()

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
            pass
