import json
import base64
import sys
from pathlib import Path


AUTOSTART_APP_NAME = "POMATO"
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

DEFAULT_CONFIG = {
    "work_start_time": "08:30",
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
            except Exception:
                self._data = DEFAULT_CONFIG.copy()
        else:
            self._data = DEFAULT_CONFIG.copy()
            self.save()

        self._sync_autostart_if_needed()

    def save(self):
        payload = dict(self._data)
        api_key = (payload.pop("api_key", "") or "").strip()
        payload["api_key_encrypted"] = self._encrypt_api_key(api_key) if api_key else ""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

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
        if sys.platform != "win32":
            return

        enabled = bool(self._data.get("autostart_enabled", True))
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                WINDOWS_RUN_KEY,
                0,
                winreg.KEY_SET_VALUE,
            )
            try:
                if enabled:
                    command = self._build_autostart_command()
                    winreg.SetValueEx(key, AUTOSTART_APP_NAME, 0, winreg.REG_SZ, command)
                else:
                    try:
                        winreg.DeleteValue(key, AUTOSTART_APP_NAME)
                    except FileNotFoundError:
                        pass
            finally:
                winreg.CloseKey(key)
        except Exception:
            # Autostart is best-effort; failures should not break app startup.
            return

    def _build_autostart_command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'

        project_root = Path(__file__).resolve().parent.parent
        main_py = project_root / "main.py"
        return f'"{sys.executable}" "{main_py}"'
