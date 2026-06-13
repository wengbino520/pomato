"""C4 US-04 — 休息结束淡入提醒窗。

半透明、右下角、淡入动画 → 10s 自动淡出 → close()。
替代系统托盘 toast 通知，提供更轻柔的过渡体验。

生命周期：TrayManager 维护单例引用，创建前清理旧窗。
"""

from PyQt6.QtCore import (
    Qt,
    QPoint,
    QPropertyAnimation,
    QTimer,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.services.logger import get_logger

logger = get_logger(__name__)

_ANIM_DURATION = 500  # ms
_AUTO_CLOSE_SEC = 10
_WINDOW_SIZE = (280, 90)


class BreakReminderWindow(QWidget):
    """半透明淡入提醒窗，右下角出现，点击或 10 秒后消失。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(*_WINDOW_SIZE)

        self._opacity = 0.0
        self._fade_in_anim: QPropertyAnimation | None = None
        self._fade_out_anim: QPropertyAnimation | None = None
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self._start_fade_out)

        self._setup_ui()
        self._position_bottom_right()

    # ── Opacity property for QPropertyAnimation ─────────────

    @pyqtProperty(float)
    def windowOpacity(self):
        return super().windowOpacity()

    @windowOpacity.setter  # type: ignore[no-redef]
    def windowOpacity(self, value: float):
        super().setWindowOpacity(value)

    def _setup_ui(self):
        self.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        title = QLabel("🍅 休息结束")
        title.setStyleSheet("color: #ff7043; font-size: 14px; font-weight: bold;")

        body = QLabel("时间到，开始新的番茄钟吧！💪")
        body.setStyleSheet("color: #ccc; font-size: 12px;")
        body.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(body)

    def _position_bottom_right(self):
        screen = self.screen()
        if screen is None:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.right() - _WINDOW_SIZE[0] - 20
            y = geo.bottom() - _WINDOW_SIZE[1] - 20
            self.move(QPoint(x, y))

    # ── Paint rounded background ───────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(40, 40, 40, 220))
        painter.setPen(QPen(QColor(80, 80, 80, 180), 1))
        painter.drawRoundedRect(self.rect(), 12, 12)
        super().paintEvent(event)

    # ── Mouse click → close ────────────────────────────────

    def mousePressEvent(self, event):
        self._auto_close_timer.stop()
        self._start_fade_out()

    # ── Lifecycle ──────────────────────────────────────────

    def show_with_fade_in(self):
        """Show with 500ms fade-in, start 10s auto-close timer."""
        self._opacity = 0.0
        self.setWindowOpacity(0.0)
        self.show()

        self._fade_in_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_in_anim.setDuration(_ANIM_DURATION)
        self._fade_in_anim.setStartValue(0.0)
        self._fade_in_anim.setEndValue(0.95)
        self._fade_in_anim.start()

        self._auto_close_timer.start(_AUTO_CLOSE_SEC * 1000)
        logger.debug("BreakReminder shown with fade-in")

    def _start_fade_out(self):
        """Fade out over 500ms, then close and delete."""
        # Prevent double-fade
        if self._fade_out_anim is not None:
            return
        self._auto_close_timer.stop()

        self._fade_out_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_out_anim.setDuration(_ANIM_DURATION)
        self._fade_out_anim.setStartValue(self.windowOpacity())
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.finished.connect(self._on_fade_out_done)
        self._fade_out_anim.start()
        logger.debug("BreakReminder fade-out started")

    def _on_fade_out_done(self):
        self.close()
        self.deleteLater()
        logger.debug("BreakReminder closed")
