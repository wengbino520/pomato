"""SettingsWindow 资料空间管理测试。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QMessageBox

from src.ui.settings_window import SettingsWindow


class TestSettingsWindowProfiles:
    def _make_config(self):
        config = MagicMock()
        config.get.side_effect = lambda key, default=None: default
        return config

    def test_window_defaults_to_wider_layout_for_profile_tab(self, qapp):
        window = SettingsWindow(self._make_config())

        assert window.width() >= 620

    def test_profile_list_loads_current_profile(self, qapp):
        profile_manager = MagicMock()
        profile_manager.list_profiles.return_value = [
            {"id": "main", "name": "主资料空间"},
            {"id": "dev-test", "name": "开发测试"},
        ]
        profile_manager.get_active_profile_id.return_value = "main"
        profile_manager.get_profile_paths.return_value.profile_dir = Path("profiles/dev-test")

        window = SettingsWindow(
            self._make_config(),
            profile_manager=profile_manager,
            current_profile_id="dev-test",
        )

        assert window.profile_list.count() == 2
        assert "开发测试" in window.current_profile_label.text()
        assert "dev-test" in window.current_profile_path_label.text()

    def test_create_profile_uses_manager_validation(self, qapp):
        profile_manager = MagicMock()
        profile_manager.list_profiles.return_value = [{"id": "main", "name": "主资料空间"}]
        profile_manager.get_active_profile_id.return_value = "main"

        window = SettingsWindow(
            self._make_config(),
            profile_manager=profile_manager,
            current_profile_id="dev-test",
        )

        with patch("src.ui.settings_window.QInputDialog.getText", return_value=("开发测试", True)), \
             patch("src.ui.settings_window.QMessageBox.information") as info_mock:
            window._create_profile()

        profile_manager.create_profile.assert_called_once_with("开发测试", source_profile_id="dev-test")
        info_mock.assert_called_once()

    def test_switch_profile_calls_restart_callback_after_confirmation(self, qapp):
        profile_manager = MagicMock()
        profile_manager.list_profiles.return_value = [
            {"id": "main", "name": "主资料空间"},
            {"id": "dev-test", "name": "开发测试"},
        ]
        profile_manager.get_active_profile_id.return_value = "main"
        on_switch_profile = MagicMock(return_value=True)

        window = SettingsWindow(
            self._make_config(),
            profile_manager=profile_manager,
            on_switch_profile=on_switch_profile,
            current_profile_id="main",
        )
        window.profile_list.setCurrentRow(1)

        with patch(
            "src.ui.settings_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            window._switch_profile()

        on_switch_profile.assert_called_once_with("dev-test")
