"""
tests/test_holiday_manager.py
HolidayManager 的正确性、边界值、异常场景测试。
"""
import json
import pytest
from datetime import date
from unittest.mock import patch, MagicMock

from src.services.holiday_manager import HolidayManager


# ── 辅助：中国节假日 API 响应格式 ────────────────────────────────────────────────

def _mock_holiday_response(year: int) -> dict:
    """构造 timor.tech API 响应格式。

    holiday=true  → 假日（不上班）
    holiday=false → 调休补班（要上班）
    """
    return {
        "code": 0,
        "holiday": {
            "01-01": {"holiday": True,  "name": "元旦"},
            "02-10": {"holiday": True,  "name": "春节"},
            "02-11": {"holiday": True,  "name": "春节"},
            "02-16": {"holiday": False, "name": "春节调休补班"},  # 周日补班
        },
    }


@pytest.fixture
def holiday_mgr(tmp_path):
    """指向临时目录的 HolidayManager，缓存隔离。"""
    return HolidayManager(tmp_path)


# ── 正确性测试 ─────────────────────────────────────────────────────────────────

class TestIsWorkday:
    """工作日判断逻辑：API 返回 > 缓存 > weekday 回退。"""

    def test_regular_monday_is_workday(self, holiday_mgr):
        """普通周一，无 API 缓存时回退到 weekday 判断。"""
        d = date(2026, 6, 1)  # Monday
        assert holiday_mgr.is_workday(d) is True

    def test_regular_saturday_not_workday(self, holiday_mgr):
        """普通周六，回退到 weekday 判断。"""
        d = date(2026, 6, 6)  # Saturday
        assert holiday_mgr.is_workday(d) is False

    def test_regular_sunday_not_workday(self, holiday_mgr):
        d = date(2026, 6, 7)  # Sunday
        assert holiday_mgr.is_workday(d) is False

    def test_holiday_from_api_not_workday(self, holiday_mgr):
        """元旦 (Jan 1) 从 API 获取，应判定为非工作日。"""
        with patch.object(holiday_mgr, "_fetch_year") as mock_fetch:
            # 预填充缓存，模拟 API 已返回
            holiday_mgr._cache = {
                "2026-01-01": {"holiday": True, "name": "元旦"},
            }
            holiday_mgr._last_fetch_year = 2026
            d = date(2026, 1, 1)
            assert holiday_mgr.is_workday(d) is False

    def test_makeup_workday_from_api_is_workday(self, holiday_mgr):
        """调休补班日（周日补班），API 返回 holiday=false，应为工作日。"""
        holiday_mgr._cache = {
            "2026-02-16": {"holiday": False, "name": "春节调休补班"},
        }
        holiday_mgr._last_fetch_year = 2026
        d = date(2026, 2, 16)  # 某周日调休补班
        assert holiday_mgr.is_workday(d) is True

    def test_cache_hit_no_api_call(self, holiday_mgr):
        """缓存命中时不发起 HTTP 请求。"""
        holiday_mgr._cache = {"2026-03-10": {"holiday": True, "name": "某节日"}}
        holiday_mgr._last_fetch_year = 2026

        with patch("urllib.request.urlopen") as mock_urlopen:
            result = holiday_mgr.is_workday(date(2026, 3, 10))
        mock_urlopen.assert_not_called()
        assert result is False

    def test_defaults_to_today_when_no_arg(self, holiday_mgr):
        """不传参数时默认为 today。"""
        today = date.today()
        result = holiday_mgr.is_workday()
        expected = today.weekday() < 5
        assert result == expected

    def test_fetch_triggered_when_cache_year_mismatch(self, holiday_mgr):
        """缓存年份不匹配时，触发 API 拉取。"""
        holiday_mgr._last_fetch_year = 2025
        d = date(2026, 6, 1)
        with patch.object(holiday_mgr, "_fetch_year") as mock_fetch:
            holiday_mgr.is_workday(d)
            mock_fetch.assert_called_once_with(2026)


class TestGetHolidayName:
    """get_holiday_name 返回值正确性。"""

    def test_holiday_date_returns_name(self, holiday_mgr):
        holiday_mgr._cache = {
            "2026-01-01": {"holiday": True, "name": "元旦"},
        }
        assert holiday_mgr.get_holiday_name(date(2026, 1, 1)) == "元旦"

    def test_workday_returns_none(self, holiday_mgr):
        holiday_mgr._cache = {
            "2026-01-05": {"holiday": False, "name": ""},
        }
        assert holiday_mgr.get_holiday_name(date(2026, 1, 5)) is None

    def test_no_cache_returns_none(self, holiday_mgr):
        assert holiday_mgr.get_holiday_name(date(2026, 3, 15)) is None

    def test_defaults_to_today(self, holiday_mgr):
        """无参数时使用今天。"""
        today = date.today()
        name = holiday_mgr.get_holiday_name()
        assert name is None  # 普通日无节日名

    def test_makeup_day_name_in_cache_returns_none(self, holiday_mgr):
        """调休补班日 holiday=false，name 存在但 get_holiday_name 仍返回 None。"""
        holiday_mgr._cache = {
            "2026-02-16": {"holiday": False, "name": "春节调休补班"},
        }
        assert holiday_mgr.get_holiday_name(date(2026, 2, 16)) is None


# ── 边界值测试 ─────────────────────────────────────────────────────────────────

class TestBoundary:
    """边界值：跨年、闰年、极值。"""

    def test_leap_year_feb_29(self, holiday_mgr):
        """闰年 2 月 29 日不崩溃（2028 是闰年）。"""
        d = date(2028, 2, 29)  # Tuesday
        assert holiday_mgr.is_workday(d) is True

    def test_new_years_eve(self, holiday_mgr):
        """跨年边界——12 月 31 日。"""
        d = date(2026, 12, 31)  # Thursday
        assert holiday_mgr.is_workday(d) is True


# ── API 异常场景测试 ────────────────────────────────────────────────────────────

class TestFetchYear:
    """_fetch_year 在 API 不可用时的容错行为。"""

    def test_fetch_network_error_does_not_crash(self, holiday_mgr):
        """网络不可达时，_fetch_year 静默失败，不抛异常。"""
        with patch("urllib.request.urlopen", side_effect=OSError("Network error")):
            holiday_mgr._fetch_year(2026)
        # 不应崩溃，缓存为空
        assert holiday_mgr._last_fetch_year is None or holiday_mgr._last_fetch_year != 2026

    def test_fetch_invalid_json_does_not_crash(self, holiday_mgr):
        """API 返回非法 JSON 时不崩溃。"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"NOT JSON"
        with patch("urllib.request.urlopen", return_value=mock_resp):
            holiday_mgr._fetch_year(2026)
        assert holiday_mgr._last_fetch_year != 2026

    def test_fetch_missing_holiday_key(self, holiday_mgr):
        """API 返回缺少 holiday 字段。"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"code": 0}).encode()
        with patch("urllib.request.urlopen", return_value=mock_resp):
            holiday_mgr._fetch_year(2026)
        # 不应崩溃，缓存应仍为空
        assert "2026-01-01" not in holiday_mgr._cache

    def test_fetch_valid_response_populates_cache(self, holiday_mgr):
        """正常 API 响应 → 正确填充缓存。"""
        mock_resp = MagicMock()
        response_data = _mock_holiday_response(2026)
        mock_resp.read.return_value = json.dumps(response_data, ensure_ascii=False).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        with patch("urllib.request.urlopen", return_value=mock_resp):
            holiday_mgr._fetch_year(2026)

        assert holiday_mgr._last_fetch_year == 2026
        assert holiday_mgr._cache.get("2026-01-01") == {"holiday": True, "name": "元旦"}
        assert holiday_mgr._cache.get("2026-02-16") == {"holiday": False, "name": "春节调休补班"}


# ── 缓存持久化测试 ──────────────────────────────────────────────────────────────

class TestCachePersistence:
    """缓存写入磁盘并正确加载。"""

    def test_cache_saved_to_disk(self, holiday_mgr):
        mock_resp = MagicMock()
        response_data = _mock_holiday_response(2026)
        mock_resp.read.return_value = json.dumps(response_data, ensure_ascii=False).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        with patch("urllib.request.urlopen", return_value=mock_resp):
            holiday_mgr._fetch_year(2026)

        assert holiday_mgr._cache_file.exists()

    def test_cache_reloaded_on_new_instance(self, tmp_path):
        """缓存写入后，新实例自动加载。"""
        mgr1 = HolidayManager(tmp_path)
        mock_resp = MagicMock()
        response_data = _mock_holiday_response(2026)
        mock_resp.read.return_value = json.dumps(response_data, ensure_ascii=False).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        with patch("urllib.request.urlopen", return_value=mock_resp):
            mgr1._fetch_year(2026)

        # 新实例
        mgr2 = HolidayManager(tmp_path)
        assert mgr2._last_fetch_year == 2026
        assert "2026-01-01" in mgr2._cache
        assert mgr2._cache["2026-01-01"]["name"] == "元旦"

    def test_corrupt_cache_file_handled_gracefully(self, tmp_path):
        """损坏的缓存文件 → 不崩溃，回退空缓存。"""
        cache_file = tmp_path / "holiday_cache.json"
        cache_file.write_text("CORRUPT{{{}}", encoding="utf-8")
        mgr = HolidayManager(tmp_path)
        assert mgr._cache == {}
        assert mgr._last_fetch_year is None

    def test_missing_cache_file_no_error(self, tmp_path):
        """缓存文件不存在 → 正常初始化。"""
        mgr = HolidayManager(tmp_path)
        assert mgr._cache == {}
        assert mgr._last_fetch_year is None


# ── force_refresh 测试 ────────────────────────────────────────────────────────

class TestForceRefresh:
    """force_refresh 强制重新拉取数据。"""

    def test_force_refresh_triggers_fetch(self, holiday_mgr):
        with patch.object(holiday_mgr, "_fetch_year") as mock_fetch:
            holiday_mgr.force_refresh()
            mock_fetch.assert_called_once_with(date.today().year)


# ── 缓存异常场景 (ID-07) ────────────────────────────────────────────────────────

class TestCacheExceptionHandling:
    """缓存读写异常不崩溃。"""

    def test_save_cache_permission_error_does_not_crash(self, holiday_mgr):
        """_save_cache 写入失败时记录警告，不抛异常。"""
        holiday_mgr._cache = {"2026-01-01": {"holiday": True, "name": "元旦"}}
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            holiday_mgr._save_cache()
        # 不应崩溃

    def test_load_cache_with_list_not_dict(self, tmp_path):
        """缓存文件内容是 JSON 数组而非对象 → 回退空缓存。"""
        import json
        cache_file = tmp_path / "holiday_cache.json"
        cache_file.write_text(json.dumps([{"holiday": True}]), encoding="utf-8")
        mgr = HolidayManager(tmp_path)
        assert mgr._cache == {}
        assert mgr._last_fetch_year is None
