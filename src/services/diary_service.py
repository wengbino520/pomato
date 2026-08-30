import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from src.services.logger import get_logger

logger = get_logger(__name__)

_DANGEROUS_BLOCK_TAGS = "script|style|iframe|object|embed|applet|meta|link"
_URL_ATTR_PATTERN = re.compile(
    r"(?P<prefix>\s(?:src|href)\s*=\s*)(?P<quote>['\"])(?P<value>.*?)(?P=quote)",
    flags=re.IGNORECASE | re.DOTALL,
)

_DEFAULT_HINTS = [
    "今天最值得记下来的一个片段是什么？",
    "今天的情绪或精力变化，最明显地出现在什么时候？",
    "如果明天要延续今天的节奏，你最想保留或改变什么？",
]


class DiaryService:
    """聚合日记页上下文与本地规则提示。"""

    def __init__(self, db, config=None):
        self.db = db
        self.config = config

    def get_daily_context(self, date_str: str) -> dict:
        diary = self.db.get_diary_entry(date_str)
        entries = self.db.get_entries_by_date(date_str)
        todos = self.db.get_todos(date_str=date_str, include_done=True)

        completed_entries = [entry for entry in entries if not entry.get("skipped")]
        done_todos = [todo for todo in todos if todo.get("status") == "done"]
        pending_todos = [todo for todo in todos if todo.get("status") != "done"]
        focus_duration = 25
        if self.config is not None:
            focus_duration = self.config.get("pomodoro_duration", 25)

        context = {
            "date": date_str,
            "pomodoro_count": len(completed_entries),
            "focus_minutes": len(completed_entries) * focus_duration,
            "todo_total": len(todos),
            "todo_done": len(done_todos),
            "todo_pending": len(pending_todos),
            "has_work_data": bool(completed_entries or todos),
            "diary_exists": diary is not None,
            "diary_word_count": diary["word_count"] if diary else 0,
            "content": diary["content"] if diary else "",
            "content_html": diary["content_html"] if diary else "",
            "attachments_json": diary["attachments_json"] if diary else [],
            "mood_score": diary["mood_score"] if diary else None,
            "mood_emoji": diary["mood_emoji"] if diary else None,
            "energy_score": diary["energy_score"] if diary else None,
            "stress_score": diary["stress_score"] if diary else None,
            "tags": diary["tags"] if diary else [],
            "updated_at": diary["updated_at"] if diary else None,
        }
        logger.debug(
            "Diary context built for %s: tomatoes=%d todos=%d diary=%s",
            date_str,
            context["pomodoro_count"],
            context["todo_total"],
            context["diary_exists"],
        )
        return context

    def save_diary_entry(self, date_str: str, **kwargs) -> dict:
        previous_entry = self.db.get_diary_entry(date_str) or {}
        content_html = kwargs.get("content_html")
        if content_html is not None:
            content_html = self._sanitize_html(content_html)
            kwargs["content_html"] = content_html
        attachments = kwargs.get("attachments_json")
        if content_html is not None:
            kwargs["attachments_json"] = self._filter_attachments_for_html(content_html, attachments)

        self.db.upsert_diary_entry(date_str, **kwargs)
        entry = self.db.get_diary_entry(date_str)
        self._cleanup_removed_attachments(
            previous_entry.get("attachments_json") or [],
            entry.get("attachments_json") if entry else [],
        )
        return entry

    @classmethod
    def _sanitize_html(cls, content_html: str) -> str:
        cleaned = content_html or ""
        cleaned = re.sub(
            rf"(?is)<({_DANGEROUS_BLOCK_TAGS})\b.*?>.*?</\1>",
            "",
            cleaned,
        )
        cleaned = re.sub(r"(?is)<(?:meta|link)\b[^>]*?/?>", "", cleaned)
        cleaned = re.sub(
            r"\s+on[a-zA-Z]+\s*=\s*(?:\".*?\"|'.*?'|[^\s>]+)",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        cleaned = re.sub(
            r"\s+style\s*=\s*(\".*?(?:expression|javascript:|vbscript:).*?\"|'.*?(?:expression|javascript:|vbscript:).*?')",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return _URL_ATTR_PATTERN.sub(cls._sanitize_url_attribute, cleaned)

    @staticmethod
    def _sanitize_url_attribute(match) -> str:
        value = match.group("value").strip()
        lowered = value.lower()
        if lowered.startswith(("javascript:", "vbscript:")):
            return ""
        if lowered.startswith("data:") and not lowered.startswith("data:image/"):
            return ""
        return match.group(0)

    @staticmethod
    def _normalize_attachment_path(path_value: str | None) -> str:
        raw_value = (path_value or "").strip()
        if not raw_value:
            return ""
        parsed = urlparse(raw_value)
        if parsed.scheme == "file":
            normalized = unquote(parsed.path)
            if re.match(r"^/[A-Za-z]:", normalized):
                normalized = normalized[1:]
        else:
            normalized = unquote(raw_value)
        return normalized.replace("\\", "/")

    @classmethod
    def _extract_image_sources(cls, content_html: str | None) -> set[str]:
        matches = re.findall(
            r"<img\b[^>]*\bsrc=['\"]([^'\"]+)['\"]",
            content_html or "",
            flags=re.IGNORECASE,
        )
        return {cls._normalize_attachment_path(match) for match in matches}

    @classmethod
    def _filter_attachments_for_html(cls, content_html: str | None, attachments: list | str | None) -> list[dict]:
        if isinstance(attachments, str):
            attachments = []
        attachments_list = list(attachments or [])
        if not attachments_list:
            return []
        referenced_sources = cls._extract_image_sources(content_html)
        if not referenced_sources:
            return []

        filtered = []
        for attachment in attachments_list:
            attachment_path = cls._normalize_attachment_path(attachment.get("path"))
            if attachment_path and attachment_path in referenced_sources:
                filtered.append(attachment)
        return filtered

    def _cleanup_removed_attachments(self, previous_attachments: list[dict], current_attachments: list[dict]):
        current_paths = {
            self._normalize_attachment_path(attachment.get("path"))
            for attachment in current_attachments
        }
        attachments_root = (self.db.data_dir / "diary_attachments").resolve()

        for attachment in previous_attachments:
            normalized_path = self._normalize_attachment_path(attachment.get("path"))
            if not normalized_path or normalized_path in current_paths:
                continue

            attachment_path = Path(normalized_path)
            if not attachment_path.is_absolute():
                attachment_path = self.db.data_dir / attachment_path

            try:
                resolved_path = attachment_path.resolve()
            except OSError:
                logger.debug("Failed to resolve diary attachment path: %s", attachment_path, exc_info=True)
                continue

            if attachments_root not in resolved_path.parents or not resolved_path.exists():
                continue

            try:
                resolved_path.unlink()
                self._prune_empty_attachment_dirs(resolved_path.parent, attachments_root)
            except OSError:
                logger.debug("Failed to remove diary attachment: %s", resolved_path, exc_info=True)

    @staticmethod
    def _prune_empty_attachment_dirs(current_dir: Path, attachments_root: Path):
        while current_dir != attachments_root:
            try:
                current_dir.rmdir()
            except OSError:
                return
            current_dir = current_dir.parent

    def get_diary_prompt_hints(self, date_str: str) -> list[str]:
        context = self.get_daily_context(date_str)
        hints: list[str] = []

        if context["pomodoro_count"] > 0:
            hints.append("今天哪一段投入最值得你复盘？")
        if context["todo_total"] > 0 and context["todo_done"] < context["todo_total"]:
            hints.append("今天有哪些计划没有按预期完成，卡点是什么？")
        if context["todo_done"] > 0:
            hints.append("今天最有成就感的一项完成是什么？")
        if context["mood_score"] is not None:
            hints.append("今天的状态评分背后，最关键的原因是什么？")
        if context["pomodoro_count"] >= 4:
            hints.append("今天最耗费精力的事情是什么，你会如何优化？")

        for default_hint in _DEFAULT_HINTS:
            if len(hints) >= 3:
                break
            if default_hint not in hints:
                hints.append(default_hint)

        return hints[:3]
