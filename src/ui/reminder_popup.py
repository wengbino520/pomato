"""
ReminderPopup — 到点提醒强弹窗 (TASK-11)

参考 PopupWindow 的 show_and_focus / _force_foreground 模式。
"""
import sys
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame,
)

from src.services.logger import get_logger

logger = get_logger(__name__)


class ReminderPopup(QDialog):
    snoozed = pyqtSignal(int)    # reminder_id
    dismissed = pyqtSignal(int)  # reminder_id

    def __init__(self, reminder_id: int, title: str, remind_time: str,
                 on_snooze=None, on_dismiss=None, parent=None):
        super().__init__(parent)
        self._reminder_id = reminder_id
        self._title = title
        self._remind_time = remind_time
        self._on_snooze_cb = on_snooze
        self._on_dismiss_cb = on_dismiss
        self._timeout_seconds = 120
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._on_timeout)
        self._setup_window()
        self._setup_ui()

    def set_timeout(self, seconds: int):
        self._timeout_seconds = max(30, seconds)

    def _setup_window(self):
        self.setWindowTitle("⏰ 提醒")
        # Dialog → Window: 避免 Linux 下输入法框架 (fcitx/ibus) 忽略弹窗
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.setMinimumWidth(380)
        self.setModal(False)
        self.setStyleSheet("QDialog { background:#fff; }")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 20)

        # ---- 图标 + 时间 ----
        header = QLabel("🔔 提醒")
        header.setStyleSheet("font-size:18px; font-weight:bold; color:#ef5350;")
        layout.addWidget(header)

        # Time
        time_label = QLabel(self._remind_time)
        time_label.setStyleSheet("font-size:32px; font-weight:bold; color:#333;")
        time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(time_label)

        # Title
        content_label = QLabel(self._title)
        content_label.setStyleSheet("font-size:15px; color:#555; padding:4px 0;")
        content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_label.setWordWrap(True)
        layout.addWidget(content_label)

        # ---- separator ----
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#eee;")
        layout.addWidget(line)

        # ---- buttons ----
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        snooze_btn = QPushButton("⏳ 延后")
        snooze_btn.setStyleSheet(
            "QPushButton { color:#666; border:1px solid #ddd; "
            "border-radius:5px; padding:8px 20px; font-size:13px; "
            "background:white; }"
            "QPushButton:hover { background:#f5f5f5; border-color:#ccc; }"
        )
        snooze_btn.clicked.connect(self._on_snooze)

        hint = QLabel("Esc=知道了")
        hint.setStyleSheet("color:#ccc; font-size:11px;")

        dismiss_btn = QPushButton("知道了")
        dismiss_btn.setDefault(True)
        dismiss_btn.setStyleSheet(
            "QPushButton { background:#ef5350; color:white; "
            "border:none; border-radius:5px; padding:8px 28px; "
            "font-size:13px; font-weight:bold; }"
            "QPushButton:hover { background:#e53935; }"
            "QPushButton:pressed { background:#c62828; }"
        )
        dismiss_btn.clicked.connect(self._on_dismiss)

        btn_layout.addWidget(snooze_btn)
        btn_layout.addWidget(hint)
        btn_layout.addStretch()
        btn_layout.addWidget(dismiss_btn)
        layout.addLayout(btn_layout)

        # Shortcuts
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._on_dismiss)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_snooze)

    def _on_snooze(self):
        self._timeout_timer.stop()
        if self._on_snooze_cb:
            self._on_snooze_cb(self._reminder_id)
        self.snoozed.emit(self._reminder_id)
        self.accept()

    def _on_dismiss(self):
        self._timeout_timer.stop()
        if self._on_dismiss_cb:
            self._on_dismiss_cb(self._reminder_id)
        self.dismissed.emit(self._reminder_id)
        self.accept()

    def _on_timeout(self):
        if not self.isVisible():
            return
        self._on_dismiss()

    # ------------------------------------------------------------------
    # Public: bring to foreground
    # ------------------------------------------------------------------

    def show_and_focus(self):
        self._timeout_timer.start(self._timeout_seconds * 1000)
        self.show()
        self.raise_()
        self.activateWindow()
        self._force_foreground()

    def _force_foreground(self):
        """Best-effort foreground window (Windows only)."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            ctypes.windll.user32.keybd_event(0, 0, 0, 0)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
