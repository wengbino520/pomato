"""
tests/test_timer_engine.py
TimerEngine 状态机、信号、暂停/恢复、自动启动逻辑的完整测试。
需要 qapp fixture（conftest.py 提供）。
"""
from datetime import datetime as _real_dt, date as _real_date
from unittest.mock import MagicMock, patch

from src.services.timer_engine import TimerState


# ── 辅助：构造 datetime/date mock ─────────────────────────────────────────────

def _dt_mocks(fixed_now: _real_dt):
    """
    返回 (mock_datetime, mock_date)，用于 patch src.timer_engine。
    mock_datetime.now() 返回 fixed_now（真实 datetime 对象）。
    mock_date.today()   返回 fixed_now.date()（真实 date 对象）。
    """
    mock_dt = MagicMock(wraps=_real_dt)
    mock_dt.now.return_value = fixed_now

    mock_d = MagicMock(wraps=_real_date)
    mock_d.today.return_value = fixed_now.date()
    return mock_dt, mock_d


# ── 正确性测试：初始状态 ──────────────────────────────────────────────────────

class TestInitialState:
    """TimerEngine 初始化后的状态应全部为默认值。"""

    def test_initial_state_is_idle(self, engine):
        assert engine.state == TimerState.IDLE

    def test_initial_session_no_is_zero(self, engine):
        assert engine.session_no == 0

    def test_initial_paused_is_false(self, engine):
        assert engine._paused is False

    def test_get_status_text_idle(self, engine):
        assert engine.get_status_text() == "空闲"


# ── 正确性测试：状态转换 ───────────────────────────────────────────────────────

class TestStateTransitions:
    """手动启动、跳过休息、停止的状态转换逻辑。"""

    def test_manual_start_from_idle_enters_work(self, engine):
        engine.manual_start()
        assert engine.state == TimerState.WORK

    def test_manual_start_increments_session_no(self, engine):
        engine.manual_start()
        assert engine.session_no == 1

    def test_manual_start_sets_remaining_from_config(self, engine, tmp_config):
        tmp_config.set("pomodoro_duration", 30)
        engine.manual_start()
        assert engine._remaining == 30 * 60

    def test_manual_start_is_noop_when_already_in_work(self, engine):
        engine.manual_start()
        engine.manual_start()        # 应忽略第二次调用
        assert engine.session_no == 1

    def test_skip_break_in_short_break_enters_work(self, engine):
        engine._state = TimerState.SHORT_BREAK
        engine._session_no = 1
        engine._session_start = "09:00:00"
        engine.skip_break()
        assert engine.state == TimerState.WORK

    def test_skip_break_in_long_break_enters_work(self, engine):
        engine._state = TimerState.LONG_BREAK
        engine._session_no = 4
        engine._session_start = "11:00:00"
        engine.skip_break()
        assert engine.state == TimerState.WORK

    def test_skip_break_in_idle_is_noop(self, engine):
        engine.skip_break()
        assert engine.state == TimerState.IDLE

    def test_skip_break_in_work_is_noop(self, engine):
        engine.manual_start()
        before = engine.session_no
        engine.skip_break()
        assert engine.state == TimerState.WORK
        assert engine.session_no == before

    def test_stop_resets_state_to_idle(self, engine):
        engine.manual_start()
        engine.stop()
        assert engine.state == TimerState.IDLE


# ── 正确性测试：休息类型判断 ──────────────────────────────────────────────────

class TestBreakLogic:
    """第 N 个番茄结束后，根据 long_break_interval 判断长/短休息。"""

    @staticmethod
    def _work_time_mocks():
        """返回 mock 的 datetime/date，时间固定在工作时段内（10:00）。"""
        fixed = _real_dt(2026, 6, 1, 10, 0, 0)
        return _dt_mocks(fixed)

    def _end_work(self, engine, session_no):
        """辅助：把引擎设置为 WORK，mock 时间后在 work_end_time 之前触发结束。"""
        engine._state = TimerState.WORK
        engine._session_no = session_no
        engine._session_start = "09:00:00"
        mock_dt, mock_d = self._work_time_mocks()
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._handle_session_end()

    def test_4th_session_triggers_long_break(self, engine, tmp_config):
        tmp_config.set("long_break_interval", 4)
        self._end_work(engine, 4)
        assert engine.state == TimerState.LONG_BREAK

    def test_non_4th_session_triggers_short_break(self, engine):
        self._end_work(engine, 1)
        assert engine.state == TimerState.SHORT_BREAK

    def test_8th_session_triggers_long_break(self, engine, tmp_config):
        tmp_config.set("long_break_interval", 4)
        self._end_work(engine, 8)
        assert engine.state == TimerState.LONG_BREAK

    def test_interval_1_every_session_is_long_break(self, engine, tmp_config):
        """interval=1：每个番茄后都是长休息。"""
        tmp_config.set("long_break_interval", 1)
        self._end_work(engine, 1)
        assert engine.state == TimerState.LONG_BREAK

    def test_short_break_duration_read_from_config(self, engine, tmp_config):
        tmp_config.set("short_break_duration", 10)
        self._end_work(engine, 1)
        assert engine._remaining == 10 * 60

    def test_long_break_duration_read_from_config(self, engine, tmp_config):
        tmp_config.set("long_break_duration", 20)
        tmp_config.set("long_break_interval", 4)
        self._end_work(engine, 4)
        assert engine._remaining == 20 * 60

    def test_short_break_end_starts_new_work_session(self, engine):
        engine._state = TimerState.SHORT_BREAK
        engine._session_no = 1
        before = engine.session_no
        mock_dt, mock_d = self._work_time_mocks()
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._handle_session_end()
        assert engine.state == TimerState.WORK
        assert engine.session_no == before + 1

    def test_long_break_end_starts_new_work_session(self, engine):
        engine._state = TimerState.LONG_BREAK
        engine._session_no = 4
        before = engine.session_no
        mock_dt, mock_d = self._work_time_mocks()
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._handle_session_end()
        assert engine.state == TimerState.WORK
        assert engine.session_no == before + 1


# ── 正确性测试：信号发射 ───────────────────────────────────────────────────────

class TestSignals:
    """关键信号在正确时机发出，携带正确参数。"""

    def test_work_session_ended_signal_emitted(self, engine):
        received = []
        engine.work_session_ended.connect(
            lambda sn, st, et: received.append((sn, st, et))
        )
        engine._state = TimerState.WORK
        engine._session_no = 2
        engine._session_start = "09:00:00"
        engine._handle_session_end()
        assert len(received) == 1
        assert received[0][0] == 2   # session_no

    def test_work_session_ended_not_emitted_during_break(self, engine):
        received = []
        engine.work_session_ended.connect(lambda *a: received.append(a))
        engine._state = TimerState.SHORT_BREAK
        engine._session_no = 1
        engine._handle_session_end()
        assert len(received) == 0

    def test_break_ended_signal_long_break_flag(self, engine):
        received = []
        engine.break_ended.connect(lambda is_long: received.append(is_long))

        engine._state = TimerState.LONG_BREAK
        engine._session_no = 4
        engine._handle_session_end()
        assert received[-1] is True

    def test_break_ended_signal_short_break_flag(self, engine):
        received = []
        engine.break_ended.connect(lambda is_long: received.append(is_long))

        engine._state = TimerState.SHORT_BREAK
        engine._session_no = 1
        engine._handle_session_end()
        assert received[-1] is False

    def test_state_changed_signal_emitted_on_manual_start(self, engine):
        received = []
        engine.state_changed.connect(lambda s: received.append(s))
        engine.manual_start()
        assert "work" in received


# ── 边界值测试：暂停/继续 ─────────────────────────────────────────────────────

class TestPauseResume:
    """暂停/继续状态切换与 tick 行为。"""

    def test_pause_resume_toggles_paused_flag(self, engine):
        assert engine._paused is False
        engine.pause_resume()
        assert engine._paused is True
        engine.pause_resume()
        assert engine._paused is False

    def test_tick_does_not_decrement_remaining_when_paused(self, engine):
        engine.manual_start()
        engine._remaining = 100
        engine.pause_resume()       # pause
        engine._on_tick()
        assert engine._remaining == 100

    def test_tick_decrements_remaining_when_running(self, engine):
        engine.manual_start()
        engine._remaining = 100
        engine._on_tick()
        assert engine._remaining == 99


# ── 边界值测试：状态文本 ──────────────────────────────────────────────────────

class TestStatusText:
    """get_status_text 在各状态下返回可读文本。"""

    def test_status_text_work_shows_time(self, engine):
        engine.manual_start()
        engine._remaining = 25 * 60
        text = engine.get_status_text()
        assert "工作" in text
        assert "25:00" in text

    def test_status_text_break_shows_time(self, engine):
        engine._state = TimerState.SHORT_BREAK
        engine._remaining = 5 * 60
        text = engine.get_status_text()
        assert "休息" in text
        assert "05:00" in text

    def test_status_text_zero_remaining(self, engine):
        engine.manual_start()
        engine._remaining = 0
        text = engine.get_status_text()
        assert "00:00" in text


# ── 异常场景测试：自动启动逻辑（mock 时间） ──────────────────────────────────

class TestAutoStart:
    """_on_tick 的 IDLE 自动启动：工作日/周末、时间前后、整点边界。
    注意：这些测试关闭节假日 API 检查，仅测试 weekday 基础逻辑。"""

    def test_auto_start_on_weekday_after_start_time(self, engine, tmp_config):
        tmp_config.set("work_start_time", "08:30")
        tmp_config.set("holiday_check_enabled", False)
        # 2026-06-01 是周一 09:00
        fixed = _real_dt(2026, 6, 1, 9, 0, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()
        assert engine.state == TimerState.WORK

    def test_no_auto_start_before_work_time(self, engine, tmp_config):
        tmp_config.set("work_start_time", "08:30")
        tmp_config.set("holiday_check_enabled", False)
        # 周一 08:00（在开始时间之前）
        fixed = _real_dt(2026, 6, 1, 8, 0, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()
        assert engine.state == TimerState.IDLE

    def test_no_auto_start_on_saturday(self, engine, tmp_config):
        tmp_config.set("work_start_time", "08:30")
        tmp_config.set("holiday_check_enabled", False)
        # 2026-06-06 是周六 09:00
        fixed = _real_dt(2026, 6, 6, 9, 0, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()
        assert engine.state == TimerState.IDLE

    def test_no_auto_start_on_sunday(self, engine, tmp_config):
        tmp_config.set("work_start_time", "08:30")
        tmp_config.set("holiday_check_enabled", False)
        # 2026-06-07 是周日 09:00
        fixed = _real_dt(2026, 6, 7, 9, 0, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()
        assert engine.state == TimerState.IDLE

    def test_auto_start_exactly_at_start_time(self, engine, tmp_config):
        """精确在 08:30:00 时应触发自动启动（>= 判断）。"""
        tmp_config.set("work_start_time", "08:30")
        tmp_config.set("holiday_check_enabled", False)
        fixed = _real_dt(2026, 6, 1, 8, 30, 0)   # 周一 08:30:00
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()
        assert engine.state == TimerState.WORK

    def test_session_no_resets_on_new_day(self, engine, tmp_config):
        """跨天后 session_no 重置为 0。"""
        tmp_config.set("work_start_time", "08:30")
        tmp_config.set("holiday_check_enabled", False)
        engine._today = "2026-06-01"
        engine._session_no = 5
        engine._state = TimerState.IDLE

        # 新的一天，但还在开始时间之前（确保不自动启动）
        fixed = _real_dt(2026, 6, 2, 7, 0, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()

        assert engine._today == "2026-06-02"
        assert engine._session_no == 0


# ── 节假日感知自动启动测试 ─────────────────────────────────────────────────

class TestAutoStartWithHoliday:
    """_on_tick IDLE 状态下，结合 HolidayManager 的工作日判断。"""

    def test_auto_start_when_holiday_manager_says_workday(self, engine, tmp_config):
        """HolidayManager 判定工作日 → 应正常启动。"""
        tmp_config.set("work_start_time", "08:30")
        fixed = _real_dt(2026, 6, 1, 9, 0, 0)  # Monday
        mock_dt, mock_d = _dt_mocks(fixed)

        with patch.object(engine._holiday_manager, "is_workday", return_value=True), \
             patch.object(engine._holiday_manager, "get_holiday_name", return_value=None), \
             patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()

        assert engine.state == TimerState.WORK

    def test_no_auto_start_on_holiday(self, engine, tmp_config):
        """元旦（周一）但 API 标记为假日 → 不启动。"""
        tmp_config.set("work_start_time", "08:30")
        fixed = _real_dt(2026, 1, 1, 9, 0, 0)  # Jan 1, 2026 (Thursday that's a holiday)
        mock_dt, mock_d = _dt_mocks(fixed)

        with patch.object(engine._holiday_manager, "is_workday", return_value=False), \
             patch.object(engine._holiday_manager, "get_holiday_name", return_value="元旦"), \
             patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()

        assert engine.state == TimerState.IDLE

    def test_workday_even_on_weekend_when_makeup(self, engine, tmp_config):
        """调休补班的周日 → holiday=false → 应启动。"""
        tmp_config.set("work_start_time", "08:30")
        fixed = _real_dt(2026, 2, 15, 9, 0, 0)  # Sunday
        mock_dt, mock_d = _dt_mocks(fixed)

        with patch.object(engine._holiday_manager, "is_workday", return_value=True), \
             patch.object(engine._holiday_manager, "get_holiday_name", return_value=None), \
             patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()

        assert engine.state == TimerState.WORK

    def test_holiday_check_disabled_uses_weekday_only(self, engine, tmp_config):
        """关闭节假日检查时，回退到纯 weekday 判断（周六不启动）。"""
        tmp_config.set("holiday_check_enabled", False)
        tmp_config.set("work_start_time", "08:30")
        fixed = _real_dt(2026, 6, 6, 9, 0, 0)  # Saturday
        mock_dt, mock_d = _dt_mocks(fixed)

        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()

        assert engine.state == TimerState.IDLE

    def test_holiday_check_disabled_weekday_starts(self, engine, tmp_config):
        """关闭节假日检查时，周一正常启动。"""
        tmp_config.set("holiday_check_enabled", False)
        tmp_config.set("work_start_time", "08:30")
        fixed = _real_dt(2026, 6, 1, 9, 0, 0)  # Monday
        mock_dt, mock_d = _dt_mocks(fixed)

        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()

        assert engine.state == TimerState.WORK

    def test_idle_tick_emits_holiday_label(self, engine, tmp_config):
        """非工作日 IDLE 状态下 tick 信号携带节日标签。"""
        tmp_config.set("work_start_time", "08:30")
        fixed = _real_dt(2026, 1, 1, 9, 0, 0)
        mock_dt, mock_d = _dt_mocks(fixed)

        labels = []
        engine.tick.connect(lambda rem, lbl: labels.append(lbl))

        with patch.object(engine._holiday_manager, "is_workday", return_value=False), \
             patch.object(engine._holiday_manager, "get_holiday_name", return_value="元旦"), \
             patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()

        assert any("元旦" in lbl for lbl in labels)

    def test_idle_tick_emits_weekend_label_when_no_holiday_name(self, engine, tmp_config):
        """普通周末（无节日名时）tick 信号显示"周末"。"""
        tmp_config.set("work_start_time", "08:30")
        fixed = _real_dt(2026, 6, 6, 9, 0, 0)  # Saturday
        mock_dt, mock_d = _dt_mocks(fixed)

        labels = []
        engine.tick.connect(lambda rem, lbl: labels.append(lbl))

        with patch.object(engine._holiday_manager, "is_workday", return_value=False), \
             patch.object(engine._holiday_manager, "get_holiday_name", return_value=None), \
             patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()

        assert any("周末" in lbl for lbl in labels)


# ── 每日计时截止时间（work_end_time）测试 ──────────────────────────────

class TestWorkEndTimeIdle:
    """IDLE 状态下 work_end_time 的边界判断。"""

    def test_no_auto_start_after_end_time(self, engine, tmp_config):
        """22:30 之后不应自动启动番茄钟。"""
        tmp_config.set("work_start_time", "08:30")
        tmp_config.set("work_end_time", "22:30")
        tmp_config.set("holiday_check_enabled", False)
        fixed = _real_dt(2026, 6, 1, 22, 31, 0)  # Monday 22:31
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()
        assert engine.state == TimerState.IDLE

    def test_no_auto_start_exactly_at_end_time(self, engine, tmp_config):
        """精确在 22:30:00 也不启动（>= 判断）。"""
        tmp_config.set("work_start_time", "08:30")
        tmp_config.set("work_end_time", "22:30")
        tmp_config.set("holiday_check_enabled", False)
        fixed = _real_dt(2026, 6, 1, 22, 30, 0)  # Monday 22:30
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()
        assert engine.state == TimerState.IDLE

    def test_auto_start_before_end_time(self, engine, tmp_config):
        """22:29 仍在工作时段内，应正常启动。"""
        tmp_config.set("work_start_time", "08:30")
        tmp_config.set("work_end_time", "22:30")
        tmp_config.set("holiday_check_enabled", False)
        fixed = _real_dt(2026, 6, 1, 22, 29, 0)  # Monday 22:29
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()
        assert engine.state == TimerState.WORK

    def test_end_time_tick_label(self, engine, tmp_config):
        """超出截止时间时 tick 信号携带正确提示。"""
        tmp_config.set("work_end_time", "22:30")
        tmp_config.set("holiday_check_enabled", False)
        fixed = _real_dt(2026, 6, 1, 22, 31, 0)
        mock_dt, mock_d = _dt_mocks(fixed)

        labels = []
        engine.tick.connect(lambda rem, lbl: labels.append(lbl))
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()
        assert any("22:30" in lbl for lbl in labels)

    def test_end_time_has_priority_over_holiday(self, engine, tmp_config):
        """截止时间判断优先于节假日判断：已过截止时间时不应显示节日标签。"""
        fixed = _real_dt(2026, 1, 1, 22, 31, 0)
        mock_dt, mock_d = _dt_mocks(fixed)

        labels = []
        engine.tick.connect(lambda rem, lbl: labels.append(lbl))

        with patch.object(engine._holiday_manager, "is_workday", return_value=False), \
             patch.object(engine._holiday_manager, "get_holiday_name", return_value="元旦"), \
             patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()

        assert not any("元旦" in lbl for lbl in labels)
        assert any("22:30" in lbl for lbl in labels)


# ── 温和截止：运行中 session 自然结束逻辑测试 ────────────────────────────

class TestGracefulEndTime:
    """工作/休息结束后先检查截止时间，不打断正在运行的 session。"""

    def _set_end_time_and_clock(self, tmp_config, engine, hour, minute, session_no=1):
        """辅助：设置截止时间 + 设置 engine 为 WORK 状态，mock 时间。"""
        tmp_config.set("work_end_time", "22:30")
        engine._state = TimerState.WORK
        engine._session_no = session_no
        engine._session_start = "22:00:00"

        fixed = _real_dt(2026, 6, 1, hour, minute, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        return mock_dt, mock_d

    def test_work_ends_after_end_time_goes_idle(self, engine, tmp_config):
        """工作番茄在截止时间后结束 → 回到 IDLE，不进入休息。"""
        mock_dt, mock_d = self._set_end_time_and_clock(
            tmp_config, engine, 22, 35
        )
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._handle_session_end()
        assert engine.state == TimerState.IDLE

    def test_work_ends_before_end_time_enters_break(self, engine, tmp_config):
        """工作番茄在截止时间前结束 → 正常进入休息。"""
        mock_dt, mock_d = self._set_end_time_and_clock(
            tmp_config, engine, 22, 10
        )
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._handle_session_end()
        assert engine.state in (TimerState.SHORT_BREAK, TimerState.LONG_BREAK)

    def test_break_ends_after_end_time_goes_idle(self, engine, tmp_config):
        """休息在截止时间后结束 → 回到 IDLE，不启动新番茄钟。"""
        tmp_config.set("work_end_time", "22:30")
        engine._state = TimerState.SHORT_BREAK
        engine._session_no = 1

        fixed = _real_dt(2026, 6, 1, 22, 35, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._handle_session_end()
        assert engine.state == TimerState.IDLE

    def test_break_ends_before_end_time_starts_new_work(self, engine, tmp_config):
        """休息在截止时间前结束 → 正常启动新番茄钟。"""
        tmp_config.set("work_end_time", "22:30")
        engine._state = TimerState.SHORT_BREAK
        engine._session_no = 1

        fixed = _real_dt(2026, 6, 1, 22, 10, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._handle_session_end()
        assert engine.state == TimerState.WORK

    def test_work_ends_after_end_time_emits_signal_and_label(self, engine, tmp_config):
        """截止后结束工作应发出 state_changed 信号和正确 tick 标签。"""
        state_changes = []
        tick_labels = []
        engine.state_changed.connect(lambda s: state_changes.append(s))
        engine.tick.connect(lambda rem, lbl: tick_labels.append(lbl))

        mock_dt, mock_d = self._set_end_time_and_clock(
            tmp_config, engine, 22, 35
        )
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._handle_session_end()

        assert "idle" in state_changes
        assert any("22:30" in lbl for lbl in tick_labels)


# ── 跨天 session_no 延迟重置测试 ────────────────────────────────────────

class TestCrossDayReset:
    """跨天时，正在运行的 session 不被打断，延迟到下次 _start_work_session 重置。"""

    def test_idle_cross_day_resets_immediately(self, engine, tmp_config):
        """IDLE 状态跨天 → session_no 立即归零。"""
        tmp_config.set("work_start_time", "08:30")
        tmp_config.set("holiday_check_enabled", False)
        engine._today = "2026-06-01"
        engine._session_no = 5

        fixed = _real_dt(2026, 6, 2, 7, 0, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()

        assert engine._session_no == 0
        assert engine._day_reset_pending is False

    def test_work_cross_day_defers_reset(self, engine, tmp_config):
        """WORK 状态跨天 → session_no 不变，标记 pending。"""
        engine._state = TimerState.WORK
        engine._session_no = 3
        engine._today = "2026-06-01"
        engine._day_reset_pending = False

        fixed = _real_dt(2026, 6, 2, 0, 5, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()

        assert engine._session_no == 3
        assert engine._day_reset_pending is True

    def test_deferred_reset_applied_on_next_start_work(self, engine):
        """pending 标记后首次 _start_work_session → session_no 归零再 +1。"""
        engine._session_no = 7
        engine._day_reset_pending = True
        engine._start_work_session()
        assert engine._session_no == 1
        assert engine._day_reset_pending is False

    def test_no_deferred_reset_without_pending(self, engine):
        """无 pending 标记时 _start_work_session 正常递增。"""
        engine._session_no = 3
        engine._day_reset_pending = False
        engine._start_work_session()
        assert engine._session_no == 4

    def test_break_cross_day_defers_reset(self, engine):
        """BREAK 状态跨天同样延迟重置。"""
        engine._state = TimerState.SHORT_BREAK
        engine._session_no = 5
        engine._remaining = 300          # 还剩 5 分钟，避免触发 _handle_session_end
        engine._today = "2026-06-01"
        engine._day_reset_pending = False

        fixed = _real_dt(2026, 6, 2, 0, 10, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()

        assert engine._session_no == 5
        assert engine._day_reset_pending is True

    def test_full_cross_day_workflow(self, engine, tmp_config):
        """完整跨天流程：WORK 跨天 → pending 标记 → 次日 _start_work_session 从 #1 开始。"""
        tmp_config.set("work_start_time", "08:30")
        tmp_config.set("holiday_check_enabled", False)
        engine._state = TimerState.WORK
        engine._session_no = 3
        engine._remaining = 300          # 确保 tick 不触发 _handle_session_end
        engine._session_start = "23:40:00"
        engine._today = "2026-06-01"
        engine._day_reset_pending = False

        # 步骤1：跨天 tick（00:05 已过午夜），session 不受影响
        fixed = _real_dt(2026, 6, 2, 0, 5, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.services.timer_engine.datetime", mock_dt), \
             patch("src.services.timer_engine.date", mock_d):
            engine._on_tick()
        assert engine._session_no == 3
        assert engine._day_reset_pending is True

        # 步骤2：手动模拟 session 结束并回到 IDLE，第二天正常自动启动
        engine._state = TimerState.IDLE
        # session_no 仍然 = 3，pending = True
        fixed2 = _real_dt(2026, 6, 2, 8, 30, 0)
        mock_dt2, mock_d2 = _dt_mocks(fixed2)
        with patch("src.services.timer_engine.datetime", mock_dt2), \
             patch("src.services.timer_engine.date", mock_d2):
            engine._on_tick()
        # _start_work_session 应检测到 pending 并归零再 +1
        assert engine.state == TimerState.WORK
        assert engine._session_no == 1
        assert engine._day_reset_pending is False
