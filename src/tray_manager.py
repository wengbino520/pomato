from datetime import date

from PyQt6.QtCore import QObject, Qt, pyqtSlot
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

from src.ai_client import AIClient
from src.main_window import MainWindow
from src.popup_window import PopupWindow
from src.report_window import ReportWindow
from src.settings_window import SettingsWindow


class TrayManager(QObject):
    def __init__(self, app, config, db, timer):
        super().__init__()
        self.app = app
        self.config = config
        self.db = db
        self.timer = timer
        self.ai_client = AIClient(config)

        self.tray: QSystemTrayIcon | None = None
        self.main_window: MainWindow | None = None

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self):
        self.tray = QSystemTrayIcon(self._make_icon("idle"))
        self.tray.setToolTip("POMATO 番茄日志")

        menu = QMenu()

        self.status_action = menu.addAction("⏱  等待中")
        self.status_action.setEnabled(False)
        menu.addSeparator()

        show_action = menu.addAction("📅  今日看板")
        show_action.triggered.connect(self.show_main_window)

        report_action = menu.addAction("📋  生成日报")
        report_action.triggered.connect(self.show_report_window)

        menu.addSeparator()

        settings_action = menu.addAction("⚙  设置")
        settings_action.triggered.connect(self.show_settings)

        menu.addSeparator()

        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(self.app.quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        # Wire timer signals
        self.timer.work_session_ended.connect(self._on_work_session_ended)
        self.timer.break_ended.connect(self._on_break_ended)
        self.timer.tick.connect(self._on_tick)
        self.timer.state_changed.connect(self._on_state_changed)

        # Pre-create main window (hidden)
        self.main_window = MainWindow(
            self.config, self.db, self.timer,
            on_generate_report=self.show_report_window,
        )

    # ------------------------------------------------------------------
    # Icon factory
    # ------------------------------------------------------------------

    @staticmethod
    def _make_icon(state: str) -> QIcon:
        size = 32
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = {"idle": "#9e9e9e", "work": "#ef5350", "break": "#66bb6a"}.get(
            state, "#ef5350"
        )
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, size - 4, size - 4)

        # Small green "leaf" when working
        if state == "work":
            painter.setBrush(QBrush(QColor("#4caf50")))
            painter.drawEllipse(11, 1, 10, 7)

        painter.end()
        return QIcon(pixmap)

    # ------------------------------------------------------------------
    # Timer signal handlers
    # ------------------------------------------------------------------

    @pyqtSlot(int, str, str)
    def _on_work_session_ended(self, session_no: int, start_time: str, end_time: str):
        self.tray.setIcon(self._make_icon("break"))
        self._show_popup(session_no, start_time, end_time)

    @pyqtSlot(bool)
    def _on_break_ended(self, is_long: bool):
        self.tray.setIcon(self._make_icon("work"))
        self.tray.showMessage(
            "POMATO",
            "休息结束，开始新的番茄钟！💪",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    @pyqtSlot(int, str)
    def _on_tick(self, remaining: int, label: str):
        if remaining >= 0:
            mins, secs = divmod(remaining, 60)
            tooltip = f"POMATO · {label}  {mins:02d}:{secs:02d}"
            self.status_action.setText(f"⏱  {label}  {mins:02d}:{secs:02d}")
        else:
            tooltip = "POMATO · 等待工作时间"
            self.status_action.setText("⏱  等待工作时间")
        self.tray.setToolTip(tooltip)

    @pyqtSlot(str)
    def _on_state_changed(self, state: str):
        if state == "work":
            self.tray.setIcon(self._make_icon("work"))
        elif state in ("short_break", "long_break"):
            self.tray.setIcon(self._make_icon("break"))

    # ------------------------------------------------------------------
    # Popup
    # ------------------------------------------------------------------

    def _show_popup(self, session_no: int, start_time: str, end_time: str):
        popup = PopupWindow(session_no, self.config)

        def on_submitted(content: str, tags: list[str]):
            today = date.today().isoformat()
            self.db.add_entry(today, session_no, start_time, end_time, content, tags)
            if self.main_window:
                self.main_window.refresh()

        def on_skipped():
            today = date.today().isoformat()
            self.db.add_entry(today, session_no, start_time, end_time, "", [], skipped=True)
            if self.main_window:
                self.main_window.refresh()

        popup.submitted.connect(on_submitted)
        popup.skipped.connect(on_skipped)
        popup.show_and_focus()

    # ------------------------------------------------------------------
    # Tray actions
    # ------------------------------------------------------------------

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_main_window()

    def show_main_window(self):
        if self.main_window:
            self.main_window.refresh()
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()

    def show_report_window(self):
        today = date.today().isoformat()
        entries = self.db.get_entries_by_date(today)
        valid = [e for e in entries if not e.get("skipped") and e.get("content")]
        if not valid:
            QMessageBox.information(
                None,
                "POMATO",
                "今日暂无有效记录，请先完成至少一个番茄钟！",
            )
            return
        win = ReportWindow(self.config, self.db, self.ai_client)
        win.exec()

    def show_settings(self):
        SettingsWindow(self.config).exec()
