
from src.services.diary_service import DiaryService


class DummyConfig:
    def __init__(self, pomodoro_duration=25):
        self._pomodoro_duration = pomodoro_duration

    def get(self, key, default=None):
        if key == "pomodoro_duration":
            return self._pomodoro_duration
        return default


class TestDiaryServiceContext:
    def test_returns_default_context_without_work_data(self, tmp_db):
        service = DiaryService(tmp_db)
        context = service.get_daily_context("2026-07-03")
        assert context["date"] == "2026-07-03"
        assert context["pomodoro_count"] == 0
        assert context["focus_minutes"] == 0
        assert context["todo_total"] == 0
        assert context["has_work_data"] is False
        assert context["diary_exists"] is False
        assert context["diary_word_count"] == 0

    def test_aggregates_entries_todos_and_diary(self, tmp_db):
        tmp_db.add_entry("2026-07-03", 1, "09:00:00", "09:25:00", "完成编码", ["开发"])
        done_id = tmp_db.add_todo("已完成", todo_date="2026-07-03")
        pending_id = tmp_db.add_todo("未完成", todo_date="2026-07-03")
        tmp_db.update_todo(done_id, status="done")
        tmp_db.upsert_diary_entry(
            "2026-07-03",
            content="今天推进顺利",
            mood_score=4,
            mood_emoji="😊",
            energy_score=3,
            stress_score=2,
            tags=["复盘"],
        )

        service = DiaryService(tmp_db, DummyConfig(pomodoro_duration=30))
        context = service.get_daily_context("2026-07-03")

        assert context["pomodoro_count"] == 1
        assert context["focus_minutes"] == 30
        assert context["todo_total"] == 2
        assert context["todo_done"] == 1
        assert context["todo_pending"] == 1
        assert context["has_work_data"] is True
        assert context["diary_exists"] is True
        assert context["content"] == "今天推进顺利"
        assert context["mood_emoji"] == "😊"
        assert context["tags"] == ["复盘"]


class TestDiaryServiceHints:
    def test_returns_default_hints_when_no_data(self, tmp_db):
        service = DiaryService(tmp_db)
        hints = service.get_diary_prompt_hints("2026-07-03")
        assert len(hints) == 3
        assert "今天最值得记下来的一个片段是什么？" in hints

    def test_returns_contextual_hints_when_work_data_exists(self, tmp_db):
        tmp_db.add_entry("2026-07-03", 1, "09:00:00", "09:25:00", "完成编码", ["开发"])
        todo_id = tmp_db.add_todo("补齐测试", todo_date="2026-07-03")
        tmp_db.upsert_diary_entry("2026-07-03", mood_score=3, mood_emoji="😐")

        service = DiaryService(tmp_db)
        hints = service.get_diary_prompt_hints("2026-07-03")

        assert len(hints) == 3
        assert any("投入" in hint for hint in hints)
        assert any("计划没有按预期完成" in hint for hint in hints)
        assert any("状态评分" in hint for hint in hints)

    def test_completed_todo_changes_hint_mix(self, tmp_db):
        todo_id = tmp_db.add_todo("写文档", todo_date="2026-07-03")
        tmp_db.update_todo(todo_id, status="done")

        service = DiaryService(tmp_db)
        hints = service.get_diary_prompt_hints("2026-07-03")

        assert any("成就感" in hint for hint in hints)
        assert not any("没有按预期完成" in hint for hint in hints)

    def test_upsert_diary_entry_preserves_rich_content_and_attachments(self, tmp_db):
        entry = tmp_db.upsert_diary_entry(
            "2026-07-03",
            content="今天做了复盘",
            content_html="<p>今天做了复盘</p><table><tr><td>结果</td></tr></table>",
            attachments_json=[{"id": "img-1", "path": "diary_attachments/2026-07-03/img-1.png"}],
        )

        assert entry["content"] == "今天做了复盘"
        assert "<table" in entry["content_html"]
        assert entry["attachments_json"] == [{"id": "img-1", "path": "diary_attachments/2026-07-03/img-1.png"}]
        assert entry["has_rich_media"] == 1
