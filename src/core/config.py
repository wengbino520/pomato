import json
import base64
import sys
from pathlib import Path

from src.services.logger import get_logger

logger = get_logger(__name__)


AUTOSTART_APP_NAME = "POMATO"
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

DEFAULT_CONFIG = {
    "work_start_time": "08:30",
    "work_end_time": "22:30",
    "pomodoro_duration": 25,
    "short_break_duration": 5,
    "long_break_duration": 15,
    "long_break_interval": 4,
    "sound_enabled": True,
    "api_base_url": "https://api.openai.com/v1",
    "api_key": "",
    "api_model": "gpt-4o-mini",
    "custom_tags": ["开发", "测试", "文档", "会议", "研究", "其他"],
    "report_system_prompt": "",
    "autostart_enabled": True,
    "popup_timeout_seconds": 180,
    "holiday_check_enabled": True,
    "reminder_silent_outside_work": False,
    "reminder_popup_timeout_seconds": 120,
    "show_completed_todos": True,
}


class Config:
    def __init__(self):
        self.data_dir = Path.home() / ".pomato"
        self.data_dir.mkdir(exist_ok=True)
        self.config_file = self.data_dir / "config.json"
        self._data = {}
        self.load()

    def load(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if not isinstance(saved, dict):
                    saved = {}
                # Backward compatibility: legacy plaintext api_key is accepted and
                # transparently converted to encrypted format on next save.
                encrypted_key = saved.pop("api_key_encrypted", "")
                if encrypted_key and not saved.get("api_key"):
                    saved["api_key"] = self._decrypt_api_key(encrypted_key)
                self._data = {**DEFAULT_CONFIG, **saved}
            except Exception as e:
                logger.warning("Config file corrupted, using defaults: %s", e)
                self._data = DEFAULT_CONFIG.copy()
        else:
            self._data = DEFAULT_CONFIG.copy()
            self.save()

        self._sync_autostart_if_needed()

    def save(self):
        payload = dict(self._data)
        api_key = (payload.pop("api_key", "") or "").strip()
        payload["api_key_encrypted"] = self._encrypt_api_key(api_key) if api_key else ""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            logger.exception("Failed to save config to %s", self.config_file)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def sync_autostart(self):
        self._sync_autostart_if_needed()

    def get_data_dir(self) -> Path:
        return self.data_dir

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _encrypt_api_key(self, value: str) -> str:
        if not value:
            return ""

        if sys.platform == "win32":
            try:
                import win32crypt
                encrypted = win32crypt.CryptProtectData(value.encode("utf-8"), "POMATO", None, None, None, 0)
                return "dpapi:" + base64.b64encode(encrypted).decode("ascii")
            except Exception:
                pass

        token = self._xor_bytes(value.encode("utf-8"))
        return "xor:" + base64.b64encode(token).decode("ascii")

    def _decrypt_api_key(self, encoded: str) -> str:
        if not encoded:
            return ""

        try:
            if encoded.startswith("dpapi:") and sys.platform == "win32":
                import win32crypt
                raw = base64.b64decode(encoded.split(":", 1)[1].encode("ascii"))
                decrypted = win32crypt.CryptUnprotectData(raw, None, None, None, 0)[1]
                return decrypted.decode("utf-8")

            if encoded.startswith("xor:"):
                raw = base64.b64decode(encoded.split(":", 1)[1].encode("ascii"))
                return self._xor_bytes(raw).decode("utf-8")

            # Compatibility fallback for very old/hand-edited config.
            return encoded
        except Exception:
            return ""

    @staticmethod
    def _xor_bytes(data: bytes) -> bytes:
        key = b"pomato-local-config-key"
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

    def _sync_autostart_if_needed(self):
        enabled = bool(self._data.get("autostart_enabled", True))
        if sys.platform == "win32":
            self._sync_autostart_windows(enabled)
        elif sys.platform.startswith("linux"):
            self._sync_autostart_linux(enabled)

    def _sync_autostart_windows(self, enabled: bool):
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                WINDOWS_RUN_KEY,
                0,
                winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
            )
            try:
                if enabled:
                    command = self._build_autostart_command()
                    winreg.SetValueEx(key, AUTOSTART_APP_NAME, 0, winreg.REG_SZ, command)
                    logger.info("Autostart registered: %s", command)
                else:
                    try:
                        winreg.DeleteValue(key, AUTOSTART_APP_NAME)
                        logger.info("Autostart removed from registry")
                    except FileNotFoundError:
                        logger.debug("Autostart key not found, nothing to remove")
            finally:
                winreg.CloseKey(key)
        except Exception:
            logger.exception("Failed to sync autostart registry key")

    def _sync_autostart_linux(self, enabled: bool):
        autostart_dir = Path.home() / ".config" / "autostart"
        desktop_file = autostart_dir / "pomato.desktop"
        try:
            if enabled:
                autostart_dir.mkdir(parents=True, exist_ok=True)
                command = self._build_autostart_command_linux()
                content = (
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    f"Name={AUTOSTART_APP_NAME}\n"
                    "Comment=POMATO 番茄日志\n"
                    f"Exec={command}\n"
                    "Terminal=false\n"
                    "X-GNOME-Autostart-enabled=true\n"
                )
                desktop_file.write_text(content, encoding="utf-8")
            else:
                if desktop_file.exists():
                    desktop_file.unlink()
        except Exception:
            pass

    def _build_autostart_command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'

        # config.py 在 src/core/ 下，需要上 3 层到项目根
        project_root = Path(__file__).resolve().parent.parent.parent
        main_py = project_root / "main.py"

        # Use pythonw.exe on Windows to suppress the console window
        python_exe = Path(sys.executable)
        if sys.platform == "win32":
            pythonw = python_exe.parent / "pythonw.exe"
            if pythonw.exists():
                python_exe = pythonw

        return f'"{python_exe}" "{main_py}"'

    def _build_autostart_command_linux(self) -> str:
        if getattr(sys, "frozen", False):
            return sys.executable

        project_root = Path(__file__).resolve().parent.parent.parent
        main_py = project_root / "main.py"
        return f"{sys.executable} {main_py}"
