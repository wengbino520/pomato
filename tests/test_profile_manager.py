"""ProfileManager 基础能力测试。"""

import json
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch

from src.core.profile_manager import ProfileManager


class TestProfileManagerPaths:
    def test_explicit_app_root_is_used(self, tmp_path):
        app_root = tmp_path / ".pomato-sandbox"
        manager = ProfileManager(app_root=app_root)

        assert manager.app_root == app_root
        assert manager.profiles_root == app_root / "profiles"
        assert manager.profiles_file == app_root / "profiles.json"
        assert manager.state_file == app_root / "profile_state.json"
        assert manager.migrations_root == app_root / "migrations"

    def test_default_app_root_uses_home_directory(self, tmp_path):
        with patch("pathlib.Path.home", return_value=tmp_path):
            manager = ProfileManager()

        assert manager.app_root == tmp_path / ".pomato"

    def test_profile_paths_are_derived_from_profile_id(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")

        paths = manager.get_profile_paths("main")

        assert paths.profile_id == "main"
        assert paths.profile_dir == manager.profiles_root / "main"
        assert paths.data_dir == manager.profiles_root / "main"
        assert paths.config_file == manager.profiles_root / "main" / "config.json"
        assert paths.db_file == manager.profiles_root / "main" / "pomato.db"
        assert paths.holiday_cache_file == manager.profiles_root / "main" / "holiday_cache.json"
        assert paths.log_dir == manager.profiles_root / "main" / "logs"
        assert paths.backup_dir == manager.profiles_root / "main" / "backups"


class TestProfileManagerInitialization:
    def test_initialization_creates_default_profile_metadata(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")

        profiles = manager.list_profiles()

        assert len(profiles) == 1
        assert profiles[0]["id"] == "main"
        assert profiles[0]["name"] == "主资料空间"
        assert profiles[0]["is_default"] is True

    def test_initialization_sets_default_active_profile(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")

        assert manager.get_active_profile_id() == "main"

    def test_set_active_profile_id_persists_state(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")
        manager.set_active_profile_id("dev-test")

        reloaded = ProfileManager(app_root=tmp_path / ".pomato")

        assert reloaded.get_active_profile_id() == "dev-test"

    def test_initialization_creates_root_directories(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")

        assert manager.app_root.exists()
        assert manager.profiles_root.exists()
        assert manager.migrations_root.exists()
        assert manager.profiles_file.exists()
        assert manager.state_file.exists()

    def test_has_profile_returns_true_for_existing_profile(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")

        assert manager.has_profile("main") is True

    def test_has_profile_returns_false_for_missing_profile(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")

        assert manager.has_profile("missing-id") is False


class TestProfileManagerValidation:
    def test_validate_profile_name_accepts_normal_name(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")

        normalized = manager.validate_profile_name("开发测试")

        assert normalized == "开发测试"

    def test_validate_profile_name_rejects_blank_name(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")

        with pytest.raises(ValueError, match="不能为空"):
            manager.validate_profile_name("   ")

    def test_validate_profile_name_rejects_leading_or_trailing_spaces(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")

        with pytest.raises(ValueError, match="前后空格"):
            manager.validate_profile_name(" 开发测试 ")

    def test_validate_profile_name_rejects_name_too_long(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")

        with pytest.raises(ValueError, match="1-32"):
            manager.validate_profile_name("a" * 33)

    def test_validate_profile_name_rejects_invalid_characters(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")

        with pytest.raises(ValueError, match="非法字符"):
            manager.validate_profile_name("dev/test")

    def test_validate_profile_name_rejects_duplicate_display_name(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")

        with pytest.raises(ValueError, match="已存在"):
            manager.validate_profile_name("主资料空间")

    def test_generate_profile_id_is_stable_slug_with_suffix(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")

        profile_id = manager.generate_profile_id("开发测试")

        assert profile_id.startswith("profile-")
        assert len(profile_id) > len("profile-")

    def test_generate_profile_id_avoids_existing_ids(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")

        first = manager.generate_profile_id("开发测试")
        second = manager.generate_profile_id("开发测试", existing_ids={first})

        assert first != second


class TestProfileManagerMutations:
    def test_create_profile_adds_registry_entry_and_directories(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")

        created = manager.create_profile("开发测试")

        assert created["name"] == "开发测试"
        assert created["id"].startswith("profile-")
        assert (manager.profiles_root / created["id"]).exists()
        assert (manager.profiles_root / created["id"] / "logs").exists()
        assert (manager.profiles_root / created["id"] / "backups").exists()
        assert any(profile["id"] == created["id"] for profile in manager.list_profiles())

    def test_create_profile_copies_safe_config_from_active_profile(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")
        active_paths = manager.get_profile_paths("main")
        active_paths.profile_dir.mkdir(parents=True, exist_ok=True)
        active_config = {
            "pomodoro_duration": 50,
            "api_key": "secret-key",
            "autostart_enabled": True,
            "custom_tags": ["开发", "实验"],
        }
        active_paths.config_file.write_text(json.dumps(active_config, ensure_ascii=False), encoding="utf-8")

        created = manager.create_profile("实验环境")
        created_paths = manager.get_profile_paths(created["id"])
        copied = json.loads(created_paths.config_file.read_text(encoding="utf-8"))

        assert copied["pomodoro_duration"] == 50
        assert copied["custom_tags"] == ["开发", "实验"]
        assert copied["api_key"] == ""
        assert copied["autostart_enabled"] is False

    def test_create_profile_can_copy_safe_config_from_specified_source_profile(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")
        created_source = manager.create_profile("开发测试")
        source_paths = manager.get_profile_paths(created_source["id"])
        source_paths.config_file.write_text(
            json.dumps(
                {
                    "pomodoro_duration": 35,
                    "custom_tags": ["测试", "隔离"],
                    "api_key": "secret-key",
                    "autostart_enabled": True,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        created = manager.create_profile("实验环境", source_profile_id=created_source["id"])
        copied = json.loads(manager.get_profile_paths(created["id"]).config_file.read_text(encoding="utf-8"))

        assert copied["pomodoro_duration"] == 35
        assert copied["custom_tags"] == ["测试", "隔离"]
        assert copied["api_key"] == ""
        assert copied["autostart_enabled"] is False

    def test_rename_profile_updates_display_name_only(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")
        created = manager.create_profile("开发测试")

        updated = manager.rename_profile(created["id"], "实验环境")

        assert updated["id"] == created["id"]
        assert updated["name"] == "实验环境"
        assert (manager.profiles_root / created["id"]).exists()

    def test_rename_profile_rejects_unknown_profile_id(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")

        with pytest.raises(ValueError, match="不存在"):
            manager.rename_profile("missing-id", "实验环境")


class TestProfileManagerLegacyBootstrap:
    def test_bootstrap_copies_legacy_root_data_to_main_profile(self, tmp_path):
        app_root = tmp_path / ".pomato"
        app_root.mkdir()
        (app_root / "config.json").write_text(
            json.dumps({"pomodoro_duration": 45}, ensure_ascii=False),
            encoding="utf-8",
        )
        legacy_db = app_root / "pomato.db"
        conn = sqlite3.connect(legacy_db)
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, title TEXT)")
        conn.execute("INSERT INTO sample (title) VALUES ('legacy')")
        conn.commit()
        conn.close()

        manager = ProfileManager(app_root=app_root)
        main_paths = manager.get_profile_paths("main")

        assert main_paths.config_file.exists()
        assert main_paths.db_file.exists()
        assert json.loads(main_paths.config_file.read_text(encoding="utf-8"))["pomodoro_duration"] == 45
        migrated = sqlite3.connect(main_paths.db_file)
        row = migrated.execute("SELECT title FROM sample").fetchone()
        migrated.close()
        assert row[0] == "legacy"
        assert legacy_db.exists()

    def test_bootstrap_copies_legacy_holiday_cache_and_sets_main_active_profile(self, tmp_path):
        app_root = tmp_path / ".pomato"
        app_root.mkdir()
        (app_root / "holiday_cache.json").write_text(
            json.dumps({"2026-01-01": {"holiday": True, "name": "元旦"}}, ensure_ascii=False),
            encoding="utf-8",
        )

        manager = ProfileManager(app_root=app_root)
        main_paths = manager.get_profile_paths("main")

        assert main_paths.holiday_cache_file.exists()
        assert json.loads(main_paths.holiday_cache_file.read_text(encoding="utf-8")) == {
            "2026-01-01": {"holiday": True, "name": "元旦"}
        }
        assert manager.get_active_profile_id() == "main"

    def test_bootstrap_writes_migration_record(self, tmp_path):
        app_root = tmp_path / ".pomato"
        app_root.mkdir()
        (app_root / "config.json").write_text("{}", encoding="utf-8")

        manager = ProfileManager(app_root=app_root)

        records = list(manager.migrations_root.glob("profile-bootstrap-*.json"))
        assert len(records) == 1
