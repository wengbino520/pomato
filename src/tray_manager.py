from datetime import date

from PyQt6.QtCore import QObject, Qt, pyqtSlot
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

from src.ai_client import AIClient
from src.history_window import HistoryWindow
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
        self._active_popup: PopupWindow | None = None

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

        history_action = menu.addAction("📚  历史日报")
        history_action.triggered.connect(self.show_history_window)

        menu.addSeparator()

        self.pause_action = menu.addAction("⏸  暂停")
        self.pause_action.triggered.connect(self._on_pause_resume)

        self.skip_break_action = menu.addAction("⏭  跳过休息")
        self.skip_break_action.triggered.connect(self.timer.skip_break)
        self.skip_break_action.setVisible(False)

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

    @staticmethod
    def _play_sound():
        """Play a notification beep; cross-platform best-effort."""
        import sys
        try:
            if sys.platform == "win32":
                import winsound
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            elif sys.platform.startswith("linux"):
                import subprocess
                # Try paplay (PulseAudio), then aplay (ALSA), then bell
                for cmd in [
                    ["paplay", "/usr/share/sounds/freedesktop/stereo/message.oga"],
                    ["aplay", "/usr/share/sounds/alsa/Front_Center.wav"],
                ]:
                    try:
                        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        return
                    except FileNotFoundError:
                        continue
                print("\a", end="", flush=True)  # terminal bell fallback
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["afplay", "/System/Library/Sounds/Ping.aiff"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

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
            self.pause_action.setVisible(True)
            self.pause_action.setText("⏸  暂停")
            self.skip_break_action.setVisible(False)
        elif state in ("short_break", "long_break"):
            self.tray.setIcon(self._make_icon("break"))
            self.pause_action.setVisible(False)
            self.skip_break_action.setVisible(True)
        else:
            self.pause_action.setVisible(False)
            self.skip_break_action.setVisible(False)

    def _on_pause_resume(self):
        self.timer.pause_resume()
        if self.timer._paused:
            self.pause_action.setText("▶  继续")
            self.tray.setIcon(self._make_icon("idle"))
        else:
            self.pause_action.setText("⏸  暂停")
            self.tray.setIcon(self._make_icon("work"))

    # ------------------------------------------------------------------
    # Popup
    # ------------------------------------------------------------------

    def _show_popup(self, session_no: int, start_time: str, end_time: str):
        # Play notification sound if enabled
        if self.config.get("sound_enabled", True):
            self._play_sound()

        today = date.today().isoformat()
        # 使用 DB 统一分配的序号，而非 TimerEngine 内部计数
        db_session_no = self.db.get_next_session_no(today)
        previous_content = self.db.get_latest_valid_entry_content(today)
        popup = PopupWindow(db_session_no, self.config, previous_content=previous_content)
        self._active_popup = popup

        def on_submitted(content: str, tags: list[str]):
            day = date.today().isoformat()
            self.db.add_entry(day, db_session_no, start_time, end_time, content, tags)
            if self.main_window:
                self.main_window.refresh()
            self._active_popup = None

        def on_skipped():
            day = date.today().isoformat()
            self.db.add_entry(day, db_session_no, start_time, end_time, "", [], skipped=True)
            if self.main_window:
                self.main_window.refresh()
            self._active_popup = None

        def on_timeout():
            day = date.today().isoformat()
            self.db.add_entry(day, db_session_no, start_time, end_time, "未记录", ["未记录"], skipped=False)
            if self.main_window:
                self.main_window.refresh()
            self.tray.showMessage(
                "POMATO",
                "本轮记录超时，已自动标记为未记录。",
                QSystemTrayIcon.MessageIcon.Warning,
                3000,
            )
            self._active_popup = None

        def on_destroyed(_obj=None):
            self._active_popup = None

        popup.submitted.connect(on_submitted)
        popup.skipped.connect(on_skipped)
        popup.timed_out.connect(on_timeout)
        popup.destroyed.connect(on_destroyed)
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

    def show_history_window(self):
        HistoryWindow(self.db).exec()
