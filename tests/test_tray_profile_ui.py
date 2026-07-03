"""TrayManager 资料空间 UI 入口测试。"""

from unittest.mock import MagicMock, patch

from src.app import TrayManager


class TestTrayProfileUi:
    def test_show_profile_settings_opens_settings_window_on_profile_tab(self, qapp):
        tray = TrayManager(
            MagicMock(),
            config=MagicMock(),
            db=MagicMock(),
            timer=MagicMock(),
            reminder_engine=MagicMock(),
            profile_manager=MagicMock(),
            runtime_args=["--profile", "main"],
            current_profile_id="main",
        )

        settings_dialog = MagicMock()
        with patch("src.app.SettingsWindow", return_value=settings_dialog) as settings_cls:
            tray.show_profile_settings()

        settings_cls.assert_called_once_with(
            tray.config,
            reminder_engine=tray._reminder_engine,
            profile_manager=tray._profile_manager,
            on_switch_profile=tray.switch_profile_and_restart,
            current_profile_id="main",
            initial_tab="profile",
        )
        settings_dialog.exec.assert_called_once()
