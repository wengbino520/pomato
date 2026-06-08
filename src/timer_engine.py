from datetime import datetime, time, date
from enum import Enum

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from src.holiday_manager import HolidayManager


class TimerState(Enum):
    IDLE = "idle"
    WORK = "work"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"


class TimerEngine(QObject):
    # session_no, start_time, end_time
    work_session_ended = pyqtSignal(int, str, str)
    # is_long_break
    break_ended = pyqtSignal(bool)
    # remaining_seconds, state_label
    tick = pyqtSignal(int, str)
    state_changed = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._state = TimerState.IDLE
        self._remaining = 0
        self._session_no = 0
        self._session_start = None
        self._today = None
        self._paused = False
        self._day_reset_pending = False
        self._holiday_manager = HolidayManager(self.config.get_data_dir())

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self._state = TimerState.IDLE

    def manual_start(self):
        if self._state == TimerState.IDLE:
            self._start_work_session()

    def skip_break(self):
        if self._state in (TimerState.SHORT_BREAK, TimerState.LONG_BREAK):
            self._start_work_session()

    def restore_session_no(self, db):
        """从数据库恢复今日已完成的番茄数，避免重启后 session_no 归零。"""
        today = date.today().isoformat()
        count = db.get_today_session_count(today)
        if count > 0:
            self._session_no = count
            self._today = today

    def pause_resume(self):
        self._paused = not self._paused

    @property
    def state(self):
        return self._state

    @property
    def session_no(self):
        return self._session_no

    def get_status_text(self):
        if self._state == TimerState.IDLE:
            return "空闲"
        if self._state == TimerState.WORK:
            mins, secs = divmod(self._remaining, 60)
            return f"工作 {mins:02d}:{secs:02d}"
        mins, secs = divmod(self._remaining, 60)
        return f"休息 {mins:02d}:{secs:02d}"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_tick(self):
        if self._paused:
            return

        now = datetime.now()
        today = date.today().isoformat()

        # Reset session count on a new calendar day (defer if a session is running)
        if self._today != today:
            if self._state == TimerState.IDLE:
                self._session_no = 0
                self._day_reset_pending = False
            else:
                self._day_reset_pending = True
            self._today = today

        if self._state == TimerState.IDLE:
            start_str = self.config.get("work_start_time", "08:30")
            end_str = self.config.get("work_end_time", "22:30")
            start_h, start_m = map(int, start_str.split(":"))
            end_h, end_m = map(int, end_str.split(":"))

            # 判断今天是否为工作日
            holiday_enabled = self.config.get("holiday_check_enabled", True)
            if holiday_enabled:
                is_workday = self._holiday_manager.is_workday(now.date())
                holiday_name = self._holiday_manager.get_holiday_name(now.date())
            else:
                is_workday = now.weekday() < 5
                holiday_name = None

            current_t = now.time()
            # 检查是否在允许的计时时间段内
            if current_t < time(start_h, start_m):
                self.tick.emit(-1, f"等待开始 ({start_str})")
            elif current_t >= time(end_h, end_m):
                self.tick.emit(-1, f"已过计时时间 (至 {end_str})")
            elif is_workday:
                self._start_work_session()
            else:
                label = f"非工作日 ({holiday_name or '周末'})"
                self.tick.emit(-1, label)
            return

        self._remaining -= 1
        if self._remaining <= 0:
            self._handle_session_end()
        else:
            labels = {
                TimerState.WORK: f"工作中 · 第{self._session_no}个番茄",
                TimerState.SHORT_BREAK: "短休息中",
                TimerState.LONG_BREAK: "长休息中",
            }
            self.tick.emit(self._remaining, labels.get(self._state, ""))

    def _start_work_session(self):
        if self._day_reset_pending:
            self._session_no = 0
            self._day_reset_pending = False
        self._session_no += 1
        self._session_start = datetime.now().strftime("%H:%M:%S")
        self._remaining = self.config.get("pomodoro_duration", 25) * 60
        self._state = TimerState.WORK
        self.state_changed.emit("work")

    def _handle_session_end(self):
        if self._state == TimerState.WORK:
            end_time = datetime.now().strftime("%H:%M:%S")
            self.work_session_ended.emit(self._session_no, self._session_start, end_time)

            # 若当前已过每日截止时间，不再进入休息，直接回到空闲
            end_str = self.config.get("work_end_time", "22:30")
            eh, em = map(int, end_str.split(":"))
            if datetime.now().time() >= time(eh, em):
                self._state = TimerState.IDLE
                self.state_changed.emit("idle")
                self.tick.emit(-1, f"已完成最后一个番茄 (已过 {end_str})")
                return

            interval = self.config.get("long_break_interval", 4)
            if self._session_no % interval == 0:
                self._state = TimerState.LONG_BREAK
                self._remaining = self.config.get("long_break_duration", 15) * 60
            else:
                self._state = TimerState.SHORT_BREAK
                self._remaining = self.config.get("short_break_duration", 5) * 60
            self.state_changed.emit(self._state.value)

        elif self._state in (TimerState.SHORT_BREAK, TimerState.LONG_BREAK):
            is_long = self._state == TimerState.LONG_BREAK
            self.break_ended.emit(is_long)

            # 若当前已过每日截止时间，不再启动新番茄钟
            end_str = self.config.get("work_end_time", "22:30")
            eh, em = map(int, end_str.split(":"))
            if datetime.now().time() >= time(eh, em):
                self._state = TimerState.IDLE
                self.state_changed.emit("idle")
                self.tick.emit(-1, f"休息结束，已过计时时间 (至 {end_str})")
                return

            self._start_work_session()
