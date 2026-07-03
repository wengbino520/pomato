"""多资料空间隔离测试。"""

from src.core.config import Config
from src.core.database import Database
from src.core.profile_manager import ProfileManager
from src.services.holiday_manager import HolidayManager


class TestProfileIsolation:
    def test_profiles_use_isolated_config_database_and_holiday_cache(self, tmp_path):
        manager = ProfileManager(app_root=tmp_path / ".pomato")
        created = manager.create_profile("开发测试")

        main_paths = manager.get_profile_paths("main")
        other_paths = manager.get_profile_paths(created["id"])

        main_config = Config(data_dir=main_paths.data_dir)
        other_config = Config(data_dir=other_paths.data_dir)
        main_config.set("pomodoro_duration", 40)
        other_config.set("pomodoro_duration", 15)

        reloaded_main_config = Config(data_dir=main_paths.data_dir)
        reloaded_other_config = Config(data_dir=other_paths.data_dir)
        assert reloaded_main_config.get("pomodoro_duration") == 40
        assert reloaded_other_config.get("pomodoro_duration") == 15

        main_db = Database(data_dir=main_paths.data_dir)
        other_db = Database(data_dir=other_paths.data_dir)
        main_entry_id = main_db.add_entry(
            "2026-07-04", 1, "09:00", "09:25", "main profile work", ["开发"]
        )
        other_db.add_entry(
            "2026-07-04", 1, "10:00", "10:25", "other profile work", ["测试"]
        )

        main_entries = main_db.get_entries_by_date("2026-07-04")
        other_entries = other_db.get_entries_by_date("2026-07-04")
        assert [entry["content"] for entry in main_entries] == ["main profile work"]
        assert [entry["content"] for entry in other_entries] == ["other profile work"]
        assert main_entry_id != other_entries[0]["id"] or main_db.db_path != other_db.db_path

        main_holiday_mgr = HolidayManager(main_paths.data_dir)
        main_holiday_mgr._cache = {"2026-01-01": {"holiday": True, "name": "元旦"}}
        main_holiday_mgr._save_cache()

        other_holiday_mgr = HolidayManager(other_paths.data_dir)
        assert other_holiday_mgr._cache == {}
        assert main_paths.holiday_cache_file.exists()
        assert other_paths.holiday_cache_file.exists() is False
