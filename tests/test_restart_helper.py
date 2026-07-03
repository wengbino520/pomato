"""restart helper 测试。"""

from unittest.mock import patch

from src.services.restart_helper import build_restart_command, restart_application


class TestRestartHelper:
    def test_build_restart_command_for_python_script(self):
        with patch("sys.executable", "C:/Python/python.exe"), \
             patch("sys.argv", ["main.py", "--profile", "dev-test"]), \
             patch("sys.frozen", False, create=True):
            command = build_restart_command(["--profile", "dev-test"])

        assert command == ["C:/Python/python.exe", "main.py", "--profile", "dev-test"]

    def test_restart_application_spawns_subprocess(self):
        with patch("src.services.restart_helper.build_restart_command", return_value=["cmd", "arg"]), \
             patch("src.services.restart_helper.subprocess.Popen") as popen_mock:
            restart_application(["--profile", "dev-test"])

        popen_mock.assert_called_once_with(["cmd", "arg"])
