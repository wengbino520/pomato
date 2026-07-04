"""
tests/test_config.py
Config 模块的正确性、边界值和异常场景测试。
"""
import json
from unittest.mock import patch

from src.core.config import Config
from src.services import logger as logger_module


# ── 正确性测试 ─────────────────────────────────────────────────────────────────

class TestConfigDefaults:
    """首次创建时，所有默认值都应正确加载。"""

    def test_default_work_start_time(self, tmp_config):
        assert tmp_config.get("work_start_time") == "08:30"

    def test_default_pomodoro_duration(self, tmp_config):
        assert tmp_config.get("pomodoro_duration") == 25

    def test_default_short_break_duration(self, tmp_config):
        assert tmp_config.get("short_break_duration") == 5

    def test_default_long_break_duration(self, tmp_config):
        assert tmp_config.get("long_break_duration") == 15

    def test_default_long_break_interval(self, tmp_config):
        assert tmp_config.get("long_break_interval") == 4

    def test_default_sound_enabled_is_true(self, tmp_config):
        assert tmp_config.get("sound_enabled") is True

    def test_default_api_key_is_empty_string(self, tmp_config):
        assert tmp_config.get("api_key") == ""

    def test_default_api_model(self, tmp_config):
        assert tmp_config.get("api_model") == "gpt-4o-mini"

    def test_default_custom_tags_contains_all_expected(self, tmp_config):
        tags = tmp_config.get("custom_tags")
        assert isinstance(tags, list)
        for expected in ["开发", "测试", "文档", "会议", "研究", "其他"]:
            assert expected in tags

    def test_default_holiday_check_enabled_is_true(self, tmp_config):
        assert tmp_config.get("holiday_check_enabled") is True

    def test_default_popup_timeout(self, tmp_config):
        assert tmp_config.get("popup_timeout_seconds") == 180


class TestConfigPersistence:
    """set() 写入磁盘，新实例重新加载后读取到正确值。"""

    def test_set_value_persists_after_reload(self, tmp_path):
        with patch("pathlib.Path.home", return_value=tmp_path):
            c = Config()
            c.set("pomodoro_duration", 30)

        # 重新创建实例，从同一路径加载
        with patch("pathlib.Path.home", return_value=tmp_path):
            c2 = Config()
        assert c2.get("pomodoro_duration") == 30

    def test_partial_config_file_merged_with_defaults(self, tmp_path):
        """磁盘上只存了一个键，重新加载后缺失键应从默认值补全。"""
        config_dir = tmp_path / ".pomato"
        config_dir.mkdir()
        (config_dir / "config.json").write_text(
            json.dumps({"pomodoro_duration": 45}), encoding="utf-8"
        )
        with patch("pathlib.Path.home", return_value=tmp_path):
            c = Config()
        assert c.get("pomodoro_duration") == 45
        assert c.get("work_start_time") == "08:30"   # 默认值被补入

    def test_set_then_get_returns_updated_value(self, tmp_config):
        tmp_config.set("pomodoro_duration", 50)
        assert tmp_config.get("pomodoro_duration") == 50

    def test_multiple_sets_last_value_wins(self, tmp_config):
        tmp_config.set("api_model", "v1")
        tmp_config.set("api_model", "v2")
        assert tmp_config.get("api_model") == "v2"

    def test_get_data_dir_points_to_pomato_subdir(self, tmp_path):
        with patch("pathlib.Path.home", return_value=tmp_path):
            c = Config()
        assert c.get_data_dir() == tmp_path / ".pomato"

    def test_config_file_created_on_first_init(self, tmp_path):
        with patch("pathlib.Path.home", return_value=tmp_path):
            Config()
        assert (tmp_path / ".pomato" / "config.json").exists()

    def test_holiday_check_persists_after_reload(self, tmp_path):
        """holiday_check_enabled 关闭后重新加载仍为 False。"""
        with patch("pathlib.Path.home", return_value=tmp_path):
            c = Config()
            c.set("holiday_check_enabled", False)

        with patch("pathlib.Path.home", return_value=tmp_path):
            c2 = Config()
        assert c2.get("holiday_check_enabled") is False

    def test_explicit_data_dir_overrides_home_directory(self, tmp_path):
        explicit_dir = tmp_path / "profiles" / "dev-test"

        with patch("pathlib.Path.home", return_value=tmp_path / "home-should-not-be-used"):
            c = Config(data_dir=explicit_dir)

        assert c.get_data_dir() == explicit_dir
        assert (explicit_dir / "config.json").exists()
        assert not (tmp_path / "home-should-not-be-used" / ".pomato" / "config.json").exists()


# ── 边界值测试 ─────────────────────────────────────────────────────────────────

class TestConfigBoundary:
    """边界值：特殊值、极值、Unicode。"""

    def test_get_nonexistent_key_returns_none(self, tmp_config):
        assert tmp_config.get("no_such_key") is None

    def test_get_nonexistent_key_with_explicit_default(self, tmp_config):
        assert tmp_config.get("no_such_key", "fallback") == "fallback"

    def test_set_zero_value_is_preserved(self, tmp_config):
        """0 是有效值，不应被当作缺失处理。"""
        tmp_config.set("pomodoro_duration", 0)
        assert tmp_config.get("pomodoro_duration") == 0

    def test_set_empty_string_is_preserved(self, tmp_config):
        tmp_config.set("api_key", "")
        assert tmp_config.get("api_key") == ""

    def test_set_list_value_round_trips(self, tmp_config):
        tags = ["α", "β", "γ"]
        tmp_config.set("custom_tags", tags)
        assert tmp_config.get("custom_tags") == tags

    def test_set_unicode_string(self, tmp_config):
        tmp_config.set("api_model", "模型-🚀")
        assert tmp_config.get("api_model") == "模型-🚀"

    def test_set_boolean_false(self, tmp_config):
        tmp_config.set("sound_enabled", False)
        assert tmp_config.get("sound_enabled") is False


# ── 异常场景测试 ───────────────────────────────────────────────────────────────

class TestConfigExceptionScenarios:
    """异常输入：损坏文件、空文件，应回退到默认值而不崩溃。"""

    def test_corrupt_json_falls_back_to_defaults(self, tmp_path):
        config_dir = tmp_path / ".pomato"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("NOT_VALID_JSON{{{{", encoding="utf-8")

        with patch("pathlib.Path.home", return_value=tmp_path):
            c = Config()
        assert c.get("pomodoro_duration") == 25

    def test_empty_json_file_falls_back_to_defaults(self, tmp_path):
        config_dir = tmp_path / ".pomato"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("", encoding="utf-8")

        with patch("pathlib.Path.home", return_value=tmp_path):
            c = Config()
        assert c.get("pomodoro_duration") == 25

    def test_json_null_value_falls_back_to_defaults(self, tmp_path):
        """文件内容为 JSON null，应回退默认值。"""
        config_dir = tmp_path / ".pomato"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("null", encoding="utf-8")

        with patch("pathlib.Path.home", return_value=tmp_path):
            c = Config()
        # null JSON loads as None; merged with DEFAULT_CONFIG should still work
        assert c.get("work_start_time") is not None


class TestLoggingSetup:
    def test_setup_logging_uses_explicit_log_dir(self, tmp_path):
        log_dir = tmp_path / "profiles" / "dev-test" / "logs"

        logger_module.setup_logging(log_dir=log_dir, force=True)

        assert logger_module.get_log_dir() == str(log_dir)
        assert (log_dir / "pomato.log").exists()
