from src.services.logger import get_logger

logger = get_logger(__name__)

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
        self.db.upsert_diary_entry(date_str, **kwargs)
        return self.db.get_diary_entry(date_str)

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
