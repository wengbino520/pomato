import json
from pathlib import Path

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
                self._data = {**DEFAULT_CONFIG, **saved}
            except Exception:
                self._data = DEFAULT_CONFIG.copy()
        else:
            self._data = DEFAULT_CONFIG.copy()
            self.save()

    def save(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def get_data_dir(self) -> Path:
        return self.data_dir
