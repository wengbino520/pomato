import json
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.config import DEFAULT_CONFIG
from src.services.logger import get_logger

logger = get_logger(__name__)

DEFAULT_APP_DIR_NAME = ".pomato"
DEFAULT_PROFILE_ID = "main"
DEFAULT_PROFILE_NAME = "主资料空间"
_PROFILE_REGISTRY_VERSION = 1
_ALLOWED_PROFILE_NAME_RE = re.compile(r"^[\u4e00-\u9fffA-Za-z0-9 _-]+$")
_PROFILE_CONFIG_COPY_EXCLUDED_KEYS = {"api_key", "autostart_enabled"}


@dataclass(frozen=True)
class ProfilePaths:
    app_root: Path
    profiles_root: Path
    profile_id: str
    profile_dir: Path
    data_dir: Path
    config_file: Path
    db_file: Path
    holiday_cache_file: Path
    log_dir: Path
    backup_dir: Path


class ProfileManager:
    def __init__(self, app_root: Path | None = None):
        self.app_root = Path(app_root) if app_root else Path.home() / DEFAULT_APP_DIR_NAME
        self.profiles_root = self.app_root / "profiles"
        self.profiles_file = self.app_root / "profiles.json"
        self.state_file = self.app_root / "profile_state.json"
        self.migrations_root = self.app_root / "migrations"

        self.app_root.mkdir(parents=True, exist_ok=True)
        self.profiles_root.mkdir(parents=True, exist_ok=True)
        self.migrations_root.mkdir(parents=True, exist_ok=True)
        self._bootstrap_legacy_root_if_needed()
        self._ensure_initialized()

    def list_profiles(self) -> list[dict[str, Any]]:
        data = self._read_json(self.profiles_file, default=self._default_profiles_payload())
        profiles = data.get("profiles", [])
        return profiles if isinstance(profiles, list) else []

    def has_profile(self, profile_id: str) -> bool:
        return any(profile.get("id") == profile_id for profile in self.list_profiles())

    def get_active_profile_id(self) -> str:
        data = self._read_json(self.state_file, default=self._default_state_payload())
        active_profile_id = data.get("active_profile_id")
        if isinstance(active_profile_id, str) and active_profile_id.strip():
            return active_profile_id
        return DEFAULT_PROFILE_ID

    def set_active_profile_id(self, profile_id: str):
        payload = {
            "active_profile_id": profile_id,
            "updated_at": datetime.now().isoformat(),
        }
        self._write_json(self.state_file, payload)

    def validate_profile_name(self, name: str, *, exclude_profile_id: str | None = None) -> str:
        if not isinstance(name, str):
            raise ValueError("资料空间名称不能为空")
        if not name.strip():
            raise ValueError("资料空间名称不能为空")
        if name != name.strip():
            raise ValueError("资料空间名称不能包含前后空格")
        if len(name) > 32:
            raise ValueError("资料空间名称长度必须在 1-32 个字符之间")
        if not _ALLOWED_PROFILE_NAME_RE.fullmatch(name):
            raise ValueError("资料空间名称包含非法字符")

        existing_names = {
            profile.get("name")
            for profile in self.list_profiles()
            if profile.get("id") != exclude_profile_id
        }
        if name in existing_names:
            raise ValueError("资料空间名称已存在")
        return name

    @staticmethod
    def generate_profile_id(name: str, existing_ids: set[str] | None = None) -> str:
        del name
        reserved = existing_ids or set()
        while True:
            profile_id = f"profile-{uuid.uuid4().hex[:8]}"
            if profile_id not in reserved:
                return profile_id

    def get_profile_paths(self, profile_id: str | None = None) -> ProfilePaths:
        resolved_profile_id = profile_id or self.get_active_profile_id()
        profile_dir = self.profiles_root / resolved_profile_id
        return ProfilePaths(
            app_root=self.app_root,
            profiles_root=self.profiles_root,
            profile_id=resolved_profile_id,
            profile_dir=profile_dir,
            data_dir=profile_dir,
            config_file=profile_dir / "config.json",
            db_file=profile_dir / "pomato.db",
            holiday_cache_file=profile_dir / "holiday_cache.json",
            log_dir=profile_dir / "logs",
            backup_dir=profile_dir / "backups",
        )

    def create_profile(self, name: str, *, source_profile_id: str | None = None) -> dict[str, Any]:
        normalized_name = self.validate_profile_name(name)
        profiles_payload = self._read_json(self.profiles_file, default=self._default_profiles_payload())
        profiles = list(profiles_payload.get("profiles", []))
        existing_ids = {profile.get("id") for profile in profiles if isinstance(profile, dict)}
        profile_id = self.generate_profile_id(normalized_name, existing_ids=existing_ids)
        created_at = datetime.now().isoformat()
        profile_record = {
            "id": profile_id,
            "name": normalized_name,
            "created_at": created_at,
            "is_default": False,
        }

        paths = self.get_profile_paths(profile_id)
        try:
            paths.profile_dir.mkdir(parents=True, exist_ok=False)
            paths.log_dir.mkdir(parents=True, exist_ok=True)
            paths.backup_dir.mkdir(parents=True, exist_ok=True)
            self._initialize_profile_config(paths, source_profile_id=source_profile_id)

            profiles.append(profile_record)
            profiles_payload["profiles"] = profiles
            self._write_json(self.profiles_file, profiles_payload)
            return profile_record
        except Exception:
            if paths.profile_dir.exists():
                shutil.rmtree(paths.profile_dir, ignore_errors=True)
            raise

    def rename_profile(self, profile_id: str, new_name: str) -> dict[str, Any]:
        normalized_name = self.validate_profile_name(new_name, exclude_profile_id=profile_id)
        profiles_payload = self._read_json(self.profiles_file, default=self._default_profiles_payload())
        profiles = profiles_payload.get("profiles", [])
        for profile in profiles:
            if profile.get("id") == profile_id:
                profile["name"] = normalized_name
                self._write_json(self.profiles_file, profiles_payload)
                return profile
        raise ValueError("资料空间不存在")

    def _ensure_initialized(self):
        if not self.profiles_file.exists():
            self._write_json(self.profiles_file, self._default_profiles_payload())
        if not self.state_file.exists():
            self._write_json(self.state_file, self._default_state_payload())

    def _bootstrap_legacy_root_if_needed(self):
        if self.profiles_file.exists() or self.state_file.exists():
            return

        legacy_files = [
            self.app_root / "config.json",
            self.app_root / "pomato.db",
            self.app_root / "holiday_cache.json",
        ]
        legacy_dirs = [
            self.app_root / "logs",
            self.app_root / "backups",
        ]
        if not any(path.exists() for path in [*legacy_files, *legacy_dirs]):
            return

        main_paths = self.get_profile_paths(DEFAULT_PROFILE_ID)
        main_paths.profile_dir.mkdir(parents=True, exist_ok=True)
        main_paths.log_dir.mkdir(parents=True, exist_ok=True)
        main_paths.backup_dir.mkdir(parents=True, exist_ok=True)

        copied_items: list[str] = []
        file_targets = {
            self.app_root / "config.json": main_paths.config_file,
            self.app_root / "pomato.db": main_paths.db_file,
            self.app_root / "holiday_cache.json": main_paths.holiday_cache_file,
        }
        dir_targets = {
            self.app_root / "logs": main_paths.log_dir,
            self.app_root / "backups": main_paths.backup_dir,
        }

        for source, target in file_targets.items():
            if source.exists():
                shutil.copy2(source, target)
                copied_items.append(source.name)
        for source, target in dir_targets.items():
            if source.exists():
                shutil.copytree(source, target, dirs_exist_ok=True)
                copied_items.append(source.name)

        self._write_json(self.profiles_file, self._default_profiles_payload())
        self._write_json(self.state_file, self._default_state_payload())
        self._write_json(
            self.migrations_root / f"profile-bootstrap-{datetime.now().strftime('%Y%m%d%H%M%S')}.json",
            {
                "type": "profile-bootstrap",
                "created_at": datetime.now().isoformat(),
                "profile_id": DEFAULT_PROFILE_ID,
                "copied_items": copied_items,
            },
        )

    def _initialize_profile_config(self, paths: ProfilePaths, *, source_profile_id: str | None = None):
        if source_profile_id is not None and not self.has_profile(source_profile_id):
            raise ValueError("资料空间不存在")

        source_config = self.get_profile_paths(source_profile_id).config_file
        payload = dict(DEFAULT_CONFIG)
        if source_config.exists():
            source_payload = self._read_json(source_config, default={})
            for key, value in source_payload.items():
                if key in DEFAULT_CONFIG and key not in _PROFILE_CONFIG_COPY_EXCLUDED_KEYS:
                    payload[key] = value
        payload["api_key"] = ""
        payload["autostart_enabled"] = False
        self._write_json(paths.config_file, payload)

    @staticmethod
    def _default_profiles_payload() -> dict[str, Any]:
        now = datetime.now().isoformat()
        return {
            "version": _PROFILE_REGISTRY_VERSION,
            "profiles": [
                {
                    "id": DEFAULT_PROFILE_ID,
                    "name": DEFAULT_PROFILE_NAME,
                    "created_at": now,
                    "is_default": True,
                }
            ],
        }

    @staticmethod
    def _default_state_payload() -> dict[str, Any]:
        return {
            "active_profile_id": DEFAULT_PROFILE_ID,
            "updated_at": datetime.now().isoformat(),
        }

    def _read_json(self, path: Path, *, default: dict[str, Any]) -> dict[str, Any]:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                return payload
        except Exception:
            logger.debug("Falling back to default JSON payload for %s", path, exc_info=True)
        return default

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
