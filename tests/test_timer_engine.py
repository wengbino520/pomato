"""
tests/test_timer_engine.py
TimerEngine 状态机、信号、暂停/恢复、自动启动逻辑的完整测试。
需要 qapp fixture（conftest.py 提供）。
"""
import pytest
from datetime import datetime as _real_dt, date as _real_date
from unittest.mock import MagicMock, patch

from src.timer_engine import TimerState


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

    def _end_work(self, engine, session_no):
        """辅助：把引擎设置为 WORK 并手动触发结束。"""
        engine._state = TimerState.WORK
        engine._session_no = session_no
        engine._session_start = "09:00:00"
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
        engine._handle_session_end()
        assert engine.state == TimerState.WORK
        assert engine.session_no == before + 1

    def test_long_break_end_starts_new_work_session(self, engine):
        engine._state = TimerState.LONG_BREAK
        engine._session_no = 4
        before = engine.session_no
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
    """_on_tick 的 IDLE 自动启动：工作日/周末、时间前后、整点边界。"""

    def test_auto_start_on_weekday_after_start_time(self, engine, tmp_config):
        tmp_config.set("work_start_time", "08:30")
        # 2026-06-01 是周一 09:00
        fixed = _real_dt(2026, 6, 1, 9, 0, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.timer_engine.datetime", mock_dt), \
             patch("src.timer_engine.date", mock_d):
            engine._on_tick()
        assert engine.state == TimerState.WORK

    def test_no_auto_start_before_work_time(self, engine, tmp_config):
        tmp_config.set("work_start_time", "08:30")
        # 周一 08:00（在开始时间之前）
        fixed = _real_dt(2026, 6, 1, 8, 0, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.timer_engine.datetime", mock_dt), \
             patch("src.timer_engine.date", mock_d):
            engine._on_tick()
        assert engine.state == TimerState.IDLE

    def test_no_auto_start_on_saturday(self, engine, tmp_config):
        tmp_config.set("work_start_time", "08:30")
        # 2026-06-06 是周六 09:00
        fixed = _real_dt(2026, 6, 6, 9, 0, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.timer_engine.datetime", mock_dt), \
             patch("src.timer_engine.date", mock_d):
            engine._on_tick()
        assert engine.state == TimerState.IDLE

    def test_no_auto_start_on_sunday(self, engine, tmp_config):
        tmp_config.set("work_start_time", "08:30")
        # 2026-06-07 是周日 09:00
        fixed = _real_dt(2026, 6, 7, 9, 0, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.timer_engine.datetime", mock_dt), \
             patch("src.timer_engine.date", mock_d):
            engine._on_tick()
        assert engine.state == TimerState.IDLE

    def test_auto_start_exactly_at_start_time(self, engine, tmp_config):
        """精确在 08:30:00 时应触发自动启动（>= 判断）。"""
        tmp_config.set("work_start_time", "08:30")
        fixed = _real_dt(2026, 6, 1, 8, 30, 0)   # 周一 08:30:00
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.timer_engine.datetime", mock_dt), \
             patch("src.timer_engine.date", mock_d):
            engine._on_tick()
        assert engine.state == TimerState.WORK

    def test_session_no_resets_on_new_day(self, engine, tmp_config):
        """跨天后 session_no 重置为 0。"""
        tmp_config.set("work_start_time", "08:30")
        engine._today = "2026-06-01"
        engine._session_no = 5
        engine._state = TimerState.IDLE

        # 新的一天，但还在开始时间之前（确保不自动启动）
        fixed = _real_dt(2026, 6, 2, 7, 0, 0)
        mock_dt, mock_d = _dt_mocks(fixed)
        with patch("src.timer_engine.datetime", mock_dt), \
             patch("src.timer_engine.date", mock_d):
            engine._on_tick()

        assert engine._today == "2026-06-02"
        assert engine._session_no == 0
