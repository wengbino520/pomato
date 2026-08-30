"""
Shared UI utilities (CD-04) — reusable helpers for dialog/window management.

Consolidates duplicated patterns from PopupWindow, ReminderPopup, ReportWindow,
HistoryWindow, and entry dialogs into a single importable module.
"""
from __future__ import annotations

import sys

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QSpinBox, QTextEdit, QWidget,
)

from src.services.logger import get_logger

logger = get_logger(__name__)


def force_foreground(widget: QWidget):
    """Best-effort foreground window activation (Windows only).

    Simulates a key event so that SetForegroundWindow is permitted by the OS,
    then calls SetForegroundWindow on the widget's native handle.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = int(widget.winId())
        ctypes.windll.user32.keybd_event(0, 0, 0, 0)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        logger.debug("force_foreground failed", exc_info=True)


def show_and_focus(dialog: QDialog, timeout_timer: QTimer,
                   timeout_seconds: int, focus_widget: QWidget | None = None):
    """Show a dialog, raise it to top, activate, force foreground, and start timeout.

    Args:
        dialog: The QDialog to show.
        timeout_timer: A single-shot QTimer for auto-timeout.
        timeout_seconds: Timeout duration in seconds.
        focus_widget: Optional widget to give keyboard focus after showing.
    """
    timeout_timer.start(timeout_seconds * 1000)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    force_foreground(dialog)
    if focus_widget is not None:
        focus_widget.setFocus()


def append_streaming_text(text_edit: QTextEdit, chunk: str):
    """Append a streaming text chunk to a QTextEdit, keeping cursor at end.

    Used by AI report generation windows for progressive display.
    """
    cursor = text_edit.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText(chunk)
    text_edit.setTextCursor(cursor)
    text_edit.ensureCursorVisible()


def setup_topmost_dialog(dialog: QDialog, min_width: int = 380):
    """Apply standard window flags for a stay-on-top, non-modal dialog.

    Sets WindowStaysOnTopHint | Window flags, enables input method,
    and disables modality. Used by PopupWindow and ReminderPopup.
    """
    dialog.setWindowFlags(
        Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window
    )
    dialog.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
    dialog.setMinimumWidth(min_width)
    dialog.setModal(False)


# ------------------------------------------------------------------
# Time entry utilities (CD-04)
# ------------------------------------------------------------------

def create_time_spinbox(suffix: str, max_val: int, value: int = 0,
                        width: int = 90) -> QSpinBox:
    """Create a configured time spinbox (hour or minute).

    Args:
        suffix: Display suffix (e.g. " 时" or " 分").
        max_val: Maximum value (23 for hours, 59 for minutes).
        value: Initial value.
        width: Fixed width in pixels.
    """
    sb = QSpinBox()
    sb.setRange(0, max_val)
    sb.setValue(value)
    sb.setSuffix(suffix)
    sb.setFixedWidth(width)
    return sb


def create_time_row(start_h: int, start_m: int, end_h: int, end_m: int):
    """Create a start/end time row with 4 spinboxes.

    Returns:
        (layout, start_hour, start_minute, end_hour, end_minute)
    """
    start_hour = create_time_spinbox(" 时", 23, start_h)
    start_minute = create_time_spinbox(" 分", 59, start_m)
    end_hour = create_time_spinbox(" 时", 23, end_h)
    end_minute = create_time_spinbox(" 分", 59, end_m)

    row = QHBoxLayout()
    row.addWidget(QLabel("开始："))
    row.addWidget(start_hour)
    row.addWidget(start_minute)
    row.addSpacing(12)
    row.addWidget(QLabel("结束："))
    row.addWidget(end_hour)
    row.addWidget(end_minute)
    row.addStretch()

    return row, start_hour, start_minute, end_hour, end_minute


def validate_time_range(start_hour: QSpinBox, start_minute: QSpinBox,
                        end_hour: QSpinBox, end_minute: QSpinBox) -> bool:
    """Validate that end time is after start time.

    Returns True if valid, False otherwise.  Caller is responsible for
    showing any warning dialog.
    """
    start_total = start_hour.value() * 60 + start_minute.value()
    end_total = end_hour.value() * 60 + end_minute.value()
    return start_total < end_total


def format_time_value(hour: QSpinBox, minute: QSpinBox) -> str:
    """Format hour/minute spinbox values as HH:MM:00 string."""
    return f"{hour.value():02d}:{minute.value():02d}:00"
