from __future__ import annotations

from collections import deque
from datetime import date

from PyQt6.QtCore import QObject, Qt, pyqtSlot
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

from src.services.ai_client import AIClient
from src.services.logger import get_logger
from src.services.restart_helper import restart_application
from src.ui.history_window import HistoryWindow
from src.ui.main_window import MainWindow
from src.ui.popup_window import PopupWindow
from src.ui.break_reminder import BreakReminderWindow
from src.ui.reminder_popup import ReminderPopup
from src.ui.report_window import ReportWindow
from src.ui.settings_window import SettingsWindow

logger = get_logger(__name__)

# 托盘图标颜色常量 (HC-02)
_STATE_COLORS = {"idle": "#9e9e9e", "work": "#ef5350", "break": "#66bb6a"}


class TrayManager(QObject):
    def __init__(self, app, config, db, timer, reminder_engine=None,
                 profile_manager=None, runtime_args=None, current_profile_id=None):
        super().__init__()
        self.app = app
        self.config = config
        self.db = db
        self.timer = timer
        self._reminder_engine = reminder_engine
        self._profile_manager = profile_manager
        self._runtime_args = list(runtime_args or [])
        self._current_profile_id = current_profile_id
        self.ai_client = AIClient(config)

        self.tray: QSystemTrayIcon | None = None
        self.main_window: MainWindow | None = None
        self._active_popup: PopupWindow | ReminderPopup | None = None
        self._popup_queue: deque[ReminderPopup] = deque(maxlen=2)
        self._break_reminder: BreakReminderWindow | None = None

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self):
        logger.info("TrayManager.setup — starting system tray")
        self.tray = QSystemTrayIcon(self._make_icon("idle"))
        self.tray.setToolTip("POMATO 番茄日志")

        menu = QMenu()

        self.status_action = menu.addAction("⏱  等待中")
        self.status_action.setEnabled(False)
        menu.addSeparator()

        show_action = menu.addAction("📅  工作看板")
        show_action.triggered.connect(self.show_main_window)

        report_action = menu.addAction("📋  生成日报")
        report_action.triggered.connect(lambda: self.show_report_window(period="daily"))

        weekly_action = menu.addAction("📋  生成周报")
        weekly_action.triggered.connect(lambda: self.show_report_window(period="weekly"))

        monthly_action = menu.addAction("📋  生成月报")
        monthly_action.triggered.connect(lambda: self.show_report_window(period="monthly"))

        history_action = menu.addAction("📚  历史报告")
        history_action.triggered.connect(self.show_history_window)

        menu.addSeparator()

        self.pause_action = menu.addAction("⏸  暂停")
        self.pause_action.triggered.connect(self._on_pause_resume)

        self.skip_break_action = menu.addAction("⏭  跳过休息")
        self.skip_break_action.triggered.connect(self.timer.skip_break)
        self.skip_break_action.setVisible(False)

        menu.addSeparator()

        if self._profile_manager:
            profile_settings_action = menu.addAction("🗂  资料空间")
            profile_settings_action.triggered.connect(self.show_profile_settings)

        settings_action = menu.addAction("⚙  设置")
        settings_action.triggered.connect(self.show_settings)

        # Pre-create main window (hidden) — 必须在菜单项之前创建
        self.main_window = MainWindow(
            self.config, self.db, self.timer,
            on_generate_report=self.show_report_window,
            on_generate_weekly_report=lambda d: self.show_report_window(target_date=d, period="weekly"),
            on_generate_monthly_report=lambda d: self.show_report_window(target_date=d, period="monthly"),
            on_open_settings=self.show_settings,
        )
        # Phase B: 注入 ReminderEngine → 初始化待办/提醒 Tab
        if self._reminder_engine:
            self.main_window.set_reminder_engine(self._reminder_engine)

        menu.addSeparator()

        # ---- TASK-16/Phase B: 待办 + 提醒菜单项 → 主窗口 Tab ----
        if self._reminder_engine:
            todo_action = menu.addAction("📋  待办")
            todo_action.triggered.connect(self.main_window.switch_to_todo_tab)
            reminder_action = menu.addAction("⏰  提醒")
            reminder_action.triggered.connect(self.main_window.switch_to_reminder_tab)
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

        # ---- TASK-17: ReminderEngine 信号接线 ----
        if self._reminder_engine:
            self._reminder_engine.reminder_triggered.connect(
                self._on_reminder_triggered
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

        color = _STATE_COLORS.get(state, _STATE_COLORS["work"])
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
                logger.debug("Terminal bell fallback (sound subsystem unavailable)")
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["afplay", "/System/Library/Sounds/Ping.aiff"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            logger.debug("Sound playback failed", exc_info=True)

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
        # US-04: 淡入提醒窗替代系统 toast
        if self._break_reminder is not None:
            self._break_reminder.close()
            self._break_reminder.deleteLater()
        self._break_reminder = BreakReminderWindow()
        self._break_reminder.show_with_fade_in()

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
        previous_content, previous_tags = self.db.get_latest_valid_entry(today)
        popup = PopupWindow(db_session_no, self.config,
                            previous_content=previous_content,
                            previous_tags=previous_tags,
                            reminder_engine=self._reminder_engine)
        self._active_popup = popup

        def on_submitted(content: str, tags: list[str], todo_id: int = 0):
            day = date.today().isoformat()
            # F7-07: pass todo_id to add_entry for bidirectional linking
            entry_id = self.db.add_entry(day, db_session_no, start_time, end_time,
                                         content, tags, todo_id=todo_id if todo_id else None)
            logger.info("Entry saved: session=%d, id=%d, tags=%s", db_session_no, entry_id, tags)
            # F7-07: link pomodoro entry to todo (status already handled by popup)
            if todo_id and entry_id and self._reminder_engine:
                self._reminder_engine.update_todo(todo_id, pomodoro_id=entry_id)
            if self.main_window:
                self.main_window.refresh()
            self._active_popup = None

        def on_skipped():
            day = date.today().isoformat()
            self.db.add_entry(day, db_session_no, start_time, end_time, "", [], skipped=True)
            logger.info("Entry skipped: session=%d", db_session_no)
            if self.main_window:
                self.main_window.refresh()
            self._active_popup = None

        def on_timeout():
            day = date.today().isoformat()
            self.db.add_entry(day, db_session_no, start_time, end_time, "未记录", ["未记录"], skipped=False)
            logger.info("Entry timed out: session=%d", db_session_no)
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
            self._show_next_queued()

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
        logger.debug("show_main_window called")
        if self.main_window:
            self.main_window.refresh()
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()

    def show_report_window(self, target_date=None, period="daily"):
        from src.ui.report_window import _get_period_range
        dt = date.fromisoformat(target_date) if target_date else date.today()
        start, end = _get_period_range(dt, period)
        logger.info("Opening %s report window for %s ~ %s", period, start, end)

        if start == end:
            entries = self.db.get_entries_by_date(start.isoformat())
        else:
            entries = self.db.get_entries_by_date_range(start.isoformat(), end.isoformat())
        valid = [e for e in entries if not e.get("skipped") and e.get("content")]
        if not valid:
            labels = {"daily": "今日", "weekly": "本周", "monthly": "本月"}
            label = labels.get(period, "该时段")
            QMessageBox.information(
                None,
                "POMATO",
                f"{label}暂无有效记录，请先完成至少一个番茄钟！",
            )
            return
        win = ReportWindow(self.config, self.db, self.ai_client,
                           report_date=dt.isoformat(), period=period)
        win.exec()

    def show_settings(self, initial_tab: str = "timer"):
        SettingsWindow(
            self.config,
            reminder_engine=self._reminder_engine,
            profile_manager=self._profile_manager,
            on_switch_profile=self.switch_profile_and_restart,
            current_profile_id=self._current_profile_id,
            initial_tab=initial_tab,
        ).exec()

    def show_profile_settings(self):
        self.show_settings(initial_tab="profile")

    def show_history_window(self):
        logger.info("Opening history window")
        HistoryWindow(self.db, ai_client=self.ai_client, config=self.config).exec()

    def switch_profile_and_restart(self, profile_id: str) -> bool:
        if self._profile_manager is None:
            raise RuntimeError("ProfileManager is not configured")
        if not self._profile_manager.has_profile(profile_id):
            raise ValueError("资料空间不存在")

        previous_profile_id = self._profile_manager.get_active_profile_id()
        self._profile_manager.set_active_profile_id(profile_id)
        try:
            restart_application(self._restart_args_after_profile_switch())
        except Exception:
            self._profile_manager.set_active_profile_id(previous_profile_id)
            logger.exception("Failed to restart after switching profile to %s", profile_id)
            return False

        self.app.quit()
        return True

    def _restart_args_after_profile_switch(self) -> list[str]:
        sanitized_args: list[str] = []
        skip_next = False
        for arg in self._runtime_args:
            if skip_next:
                skip_next = False
                continue
            if arg == "--profile":
                skip_next = True
                continue
            if arg.startswith("--profile="):
                continue
            sanitized_args.append(arg)
        return sanitized_args

    # ------------------------------------------------------------------
    # TASK-15/16/17: Reminder popup queue + dialog launchers
    # ------------------------------------------------------------------

    @pyqtSlot(int, str, str)
    def _on_reminder_triggered(self, reminder_id: int, title: str, remind_time: str):
        logger.info("Reminder popup shown: id=%d, title=%s", reminder_id, title)
        popup = ReminderPopup(
            reminder_id, title, remind_time,
            on_snooze=self._on_reminder_snoozed,
            on_dismiss=self._on_reminder_dismissed,
        )
        timeout = self.config.get("reminder_popup_timeout_seconds", 120)
        popup.set_timeout(timeout)

        if self._active_popup is None:
            self._active_popup = popup
            popup.destroyed.connect(lambda: self._on_popup_closed())
            popup.show_and_focus()
        else:
            self._popup_queue.append(popup)

    def _on_popup_closed(self):
        self._active_popup = None
        self._show_next_queued()

    def _show_next_queued(self):
        if self._active_popup is not None:
            return
        while self._popup_queue:
            popup = self._popup_queue.popleft()
            if popup.isVisible():
                continue
            self._active_popup = popup
            popup.destroyed.connect(lambda: self._on_popup_closed())
            popup.show_and_focus()
            return

    def _on_reminder_snoozed(self, reminder_id: int):
        logger.info("Reminder snoozed: id=%d", reminder_id)
        if self._reminder_engine:
            self._reminder_engine.snooze_reminder(reminder_id)

    def _on_reminder_dismissed(self, reminder_id: int):
        logger.debug("Reminder dismissed: id=%d", reminder_id)
        pass  # Already marked triggered in engine
