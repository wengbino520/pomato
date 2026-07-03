"""main.py 启动参数与运行时上下文测试。"""

import pytest
from unittest.mock import MagicMock, patch

import main
from src.core.profile_manager import ProfileManager


class TestRuntimeArgs:
    def test_data_dir_takes_priority_over_profile(self, tmp_path):
        explicit_dir = tmp_path / "sandbox"
        app_root = tmp_path / ".pomato"
        manager = ProfileManager(app_root=app_root)
        manager.create_profile("开发测试")

        context = main.resolve_runtime_context(
            ["--profile", "main", "--data-dir", str(explicit_dir)],
            app_root=app_root,
        )

        assert context.data_dir == explicit_dir
        assert context.source == "data-dir"
        assert context.profile_id is None

    def test_profile_argument_uses_registered_profile(self, tmp_path):
        app_root = tmp_path / ".pomato"
        manager = ProfileManager(app_root=app_root)
        created = manager.create_profile("开发测试")

        context = main.resolve_runtime_context(
            ["--profile", created["id"]],
            app_root=app_root,
        )

        assert context.profile_id == created["id"]
        assert context.data_dir == app_root / "profiles" / created["id"]
        assert context.source == "profile"

    def test_missing_profile_argument_fails_fast(self, tmp_path):
        app_root = tmp_path / ".pomato"
        ProfileManager(app_root=app_root)

        with pytest.raises(ValueError, match="不存在"):
            main.resolve_runtime_context(["--profile", "missing-id"], app_root=app_root)

    def test_active_profile_is_used_by_default(self, tmp_path):
        app_root = tmp_path / ".pomato"
        manager = ProfileManager(app_root=app_root)
        created = manager.create_profile("开发测试")
        manager.set_active_profile_id(created["id"])

        context = main.resolve_runtime_context([], app_root=app_root)

        assert context.profile_id == created["id"]
        assert context.data_dir == app_root / "profiles" / created["id"]
        assert context.source == "active-profile"


class TestMainBootstrapping:
    def test_main_uses_resolved_runtime_context_for_object_graph(self, tmp_path):
        data_dir = tmp_path / "profiles" / "dev-test"
        context = main.RuntimeContext(
            data_dir=data_dir,
            log_dir=data_dir / "logs",
            profile_id="dev-test",
            source="profile",
            profile_manager=None,
        )

        fake_app = MagicMock()
        fake_app.exec.return_value = 0
        fake_timer = MagicMock()
        fake_tray = MagicMock()

        with patch("main.resolve_runtime_context", return_value=context), \
             patch("main.setup_logging") as setup_logging_mock, \
             patch("main.QApplication", return_value=fake_app), \
             patch("src.core.config.Config") as config_cls, \
             patch("src.core.database.Database") as database_cls, \
             patch("src.services.reminder_engine.ReminderEngine") as reminder_cls, \
             patch("src.services.timer_engine.TimerEngine", return_value=fake_timer) as timer_cls, \
             patch("src.app.TrayManager", return_value=fake_tray) as tray_cls, \
             patch("sys.exit") as sys_exit_mock:
            config_instance = config_cls.return_value
            database_instance = database_cls.return_value
            reminder_instance = reminder_cls.return_value

            main.main(["--profile", "dev-test"])

        setup_logging_mock.assert_called_once_with(log_dir=data_dir / "logs", force=True)
        config_cls.assert_called_once_with(data_dir=data_dir)
        database_cls.assert_called_once_with(data_dir=data_dir)
        reminder_cls.assert_called_once_with(config_instance, database_instance)
        timer_cls.assert_called_once_with(config_instance, reminder_engine=reminder_instance)
        tray_cls.assert_called_once_with(
            fake_app,
            config_instance,
            database_instance,
            fake_timer,
            reminder_engine=reminder_instance,
            profile_manager=None,
            runtime_args=["--profile", "dev-test"],
            current_profile_id="dev-test",
        )
        fake_timer.restore_session_no.assert_called_once_with(database_instance)
        fake_timer.start.assert_called_once()
        fake_tray.setup.assert_called_once()
        sys_exit_mock.assert_called_once_with(0)
