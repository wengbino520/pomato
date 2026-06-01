import ctypes

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
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
    submitted = pyqtSignal(str, list)   # content, tags
    skipped = pyqtSignal()

    def __init__(self, session_no: int, config, parent=None):
        super().__init__(parent)
        self.session_no = session_no
        self.config = config
        self.selected_tags: list[str] = []
        self._setup_window()
        self._setup_ui()

    # ------------------------------------------------------------------
    # Window flags
    # ------------------------------------------------------------------

    def _setup_window(self):
        self.setWindowTitle(f"POMATO · 第{self.session_no}个番茄钟完成")
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog
        )
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
        content = self.text_edit.toPlainText().strip()
        if not content:
            self.text_edit.setStyleSheet(
                self.text_edit.styleSheet() + "border-color: #ef5350;"
            )
            self.text_edit.setFocus()
            return
        self.submitted.emit(content, list(self.selected_tags))
        self.accept()

    def _on_skip(self):
        self.skipped.emit()
        self.reject()

    # ------------------------------------------------------------------
    # Public: bring to foreground
    # ------------------------------------------------------------------

    def show_and_focus(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self._force_foreground()
        self.text_edit.setFocus()

    def _force_foreground(self):
        """Best-effort Windows foreground window."""
        try:
            hwnd = int(self.winId())
            # Simulate a key event so SetForegroundWindow is allowed
            ctypes.windll.user32.keybd_event(0, 0, 0, 0)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
