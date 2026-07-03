"""TrayManager 资料空间切换测试。"""

from unittest.mock import MagicMock, patch

from src.app import TrayManager


class TestTrayProfileSwitch:
    def test_switch_profile_and_restart_updates_state_and_quits(self, qapp):
        app = MagicMock()
        profile_manager = MagicMock()
        profile_manager.has_profile.return_value = True
        profile_manager.get_active_profile_id.return_value = "main"

        tray = TrayManager(
            app,
            config=MagicMock(),
            db=MagicMock(),
            timer=MagicMock(),
            reminder_engine=None,
            profile_manager=profile_manager,
            runtime_args=["--profile", "main"],
        )

        with patch("src.app.restart_application") as restart_mock:
            result = tray.switch_profile_and_restart("dev-test")

        assert result is True
        profile_manager.set_active_profile_id.assert_called_once_with("dev-test")
        restart_mock.assert_called_once_with([])
        app.quit.assert_called_once()

    def test_switch_profile_and_restart_restores_previous_state_on_failure(self, qapp):
        app = MagicMock()
        profile_manager = MagicMock()
        profile_manager.has_profile.return_value = True
        profile_manager.get_active_profile_id.return_value = "main"

        tray = TrayManager(
            app,
            config=MagicMock(),
            db=MagicMock(),
            timer=MagicMock(),
            reminder_engine=None,
            profile_manager=profile_manager,
            runtime_args=["--profile", "main"],
        )

        with patch("src.app.restart_application", side_effect=RuntimeError("boom")):
            result = tray.switch_profile_and_restart("dev-test")

        assert result is False
        assert profile_manager.set_active_profile_id.call_count == 2
        profile_manager.set_active_profile_id.assert_any_call("dev-test")
        profile_manager.set_active_profile_id.assert_any_call("main")
        app.quit.assert_not_called()
