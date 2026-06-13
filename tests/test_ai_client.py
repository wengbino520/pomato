"""
tests/test_ai_client.py
build_prompt 和 AIClient.generate_report 的正确性、边界值和异常场景测试。
"""
import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from src.services.ai_client import build_prompt, AIClient, _format_todo_summary


# ── 辅助：构造测试用 entry ────────────────────────────────────────────────────

def make_entry(session_no=1, start="09:00:00", end="09:25:00",
               content="测试内容", tags=None, skipped=False):
    return {
        "session_no": session_no,
        "start_time": start,
        "end_time": end,
        "content": content,
        "tags": tags if tags is not None else [],
        "skipped": skipped,
    }


# ── 正确性测试：build_prompt ──────────────────────────────────────────────────

class TestBuildPrompt:
    """build_prompt 输出的内容正确性。"""

    def test_contains_specified_report_date(self):
        prompt = build_prompt([], "2026年06月02日")
        assert "2026年06月02日" in prompt

    def test_defaults_to_today_when_date_is_none(self):
        today = date.today().strftime("%Y年%m月%d日")
        prompt = build_prompt([])
        assert today in prompt

    def test_valid_entry_content_appears_in_prompt(self):
        entry = make_entry(content="完成了用户登录功能")
        prompt = build_prompt([entry])
        assert "完成了用户登录功能" in prompt

    def test_skipped_entry_excluded_from_prompt(self):
        entry = make_entry(content="被跳过的内容", skipped=True)
        prompt = build_prompt([entry])
        assert "被跳过的内容" not in prompt

    def test_empty_content_entry_excluded(self):
        entry = make_entry(content="")
        prompt = build_prompt([entry])
        # 时间段格式不应出现（因为该条目被过滤掉）
        assert "09:00-09:25" not in prompt

    def test_none_content_entry_excluded(self):
        entry = make_entry(content=None)
        # 不应崩溃，且该条目不出现在提示中
        prompt = build_prompt([entry])
        assert "09:00-09:25" not in prompt

    def test_tags_appear_in_bracket_format(self):
        entry = make_entry(content="任务", tags=["开发", "测试"])
        prompt = build_prompt([entry])
        assert "[开发, 测试]" in prompt

    def test_empty_tags_bracket_not_shown(self):
        entry = make_entry(content="任务", tags=[])
        prompt = build_prompt([entry])
        assert "[]" not in prompt

    def test_single_tag_formatted_correctly(self):
        entry = make_entry(content="任务", tags=["会议"])
        prompt = build_prompt([entry])
        assert "[会议]" in prompt

    def test_pomodoro_count_is_correct(self):
        entries = [make_entry(session_no=i, content="T") for i in range(1, 4)]
        prompt = build_prompt(entries)
        assert "3 个番茄钟" in prompt

    def test_focus_minutes_is_count_times_25(self):
        """3 个番茄钟 → 75 分钟。"""
        entries = [make_entry(session_no=i, content="T") for i in range(1, 4)]
        prompt = build_prompt(entries)
        assert "75 分钟" in prompt

    def test_time_formatted_as_hh_mm(self):
        entry = make_entry(start="09:05:30", end="09:30:45", content="任务")
        prompt = build_prompt([entry])
        assert "09:05-09:30" in prompt


# ── 边界值测试：build_prompt ──────────────────────────────────────────────────

class TestBuildPromptBoundary:
    """边界值：空列表、全 skipped、单条、多 tag。"""

    def test_empty_entries_shows_zero_pomodoros(self):
        prompt = build_prompt([])
        assert "0 个番茄钟" in prompt

    def test_empty_entries_shows_zero_minutes(self):
        prompt = build_prompt([])
        assert "0 分钟" in prompt

    def test_all_skipped_shows_zero_pomodoros(self):
        entries = [make_entry(content="T", skipped=True) for _ in range(3)]
        prompt = build_prompt(entries)
        assert "0 个番茄钟" in prompt

    def test_mixed_skipped_and_valid_counts_only_valid(self):
        entries = [
            make_entry(session_no=1, content="有效"),
            make_entry(session_no=2, content="跳过", skipped=True),
            make_entry(session_no=3, content="有效2"),
        ]
        prompt = build_prompt(entries)
        assert "2 个番茄钟" in prompt
        assert "有效" in prompt
        assert "跳过" not in prompt

    def test_many_tags_all_appear(self):
        tags = ["开发", "测试", "文档", "会议"]
        entry = make_entry(content="多标签任务", tags=tags)
        prompt = build_prompt([entry])
        for t in tags:
            assert t in prompt


# ── 异常场景测试：generate_report ────────────────────────────────────────────

class TestGenerateReport:
    """generate_report：API Key 缺失应报错；正常调用验证参数传递。"""

    def test_raises_value_error_when_api_key_empty(self, tmp_config):
        tmp_config.set("api_key", "")
        client = AIClient(tmp_config)
        with pytest.raises(ValueError, match="API Key"):
            client.generate_report([])

    def test_raises_value_error_when_api_key_is_none(self, tmp_config):
        tmp_config.set("api_key", None)
        client = AIClient(tmp_config)
        with pytest.raises(ValueError):
            client.generate_report([])

    def test_local_ollama_allows_empty_api_key(self, tmp_config):
        tmp_config.set("api_key", "")
        tmp_config.set("api_base_url", "http://localhost:11434/v1")

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "ok"
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        with patch("src.services.ai_client.OpenAI", return_value=mock_client):
            result = AIClient(tmp_config).generate_report([make_entry(content="任务")])

        assert result == "ok"

    def test_non_streaming_calls_openai_with_correct_model(self, tmp_config):
        """非流式调用：使用配置中的 model 名称。"""
        tmp_config.set("api_key", "sk-test")
        tmp_config.set("api_model", "custom-model-v2")

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "# 日报内容"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        with patch("src.services.ai_client.OpenAI", return_value=mock_client):
            result = AIClient(tmp_config).generate_report(
                [make_entry(content="任务")]
            )

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "custom-model-v2"
        assert result == "# 日报内容"

    def test_non_streaming_passes_system_and_user_messages(self, tmp_config):
        """请求中应包含 system prompt 和用户内容。"""
        tmp_config.set("api_key", "sk-test")

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "ok"
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        with patch("src.services.ai_client.OpenAI", return_value=mock_client):
            AIClient(tmp_config).generate_report([make_entry(content="任务")])

        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        roles = [m["role"] for m in messages]
        assert "system" in roles
        assert "user" in roles

    def test_streaming_invokes_on_chunk_callback(self, tmp_config):
        """流式调用：每个有效 delta 都触发 on_chunk，最终返回拼接结果。"""
        tmp_config.set("api_key", "sk-test")

        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "## 日报\n"

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = "完成开发任务。"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter([chunk1, chunk2])

        received_chunks = []
        with patch("src.services.ai_client.OpenAI", return_value=mock_client):
            result = AIClient(tmp_config).generate_report(
                [make_entry(content="任务")],
                on_chunk=lambda c: received_chunks.append(c),
            )

        assert received_chunks == ["## 日报\n", "完成开发任务。"]
        assert result == "## 日报\n完成开发任务。"

    def test_streaming_skips_empty_delta_chunks(self, tmp_config):
        """流式调用：delta 为空字符串/None 时不触发 on_chunk。"""
        tmp_config.set("api_key", "sk-test")

        chunk_empty = MagicMock()
        chunk_empty.choices = [MagicMock()]
        chunk_empty.choices[0].delta.content = ""   # 空 delta

        chunk_valid = MagicMock()
        chunk_valid.choices = [MagicMock()]
        chunk_valid.choices[0].delta.content = "内容"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter([chunk_empty, chunk_valid])

        received_chunks = []
        with patch("src.services.ai_client.OpenAI", return_value=mock_client):
            AIClient(tmp_config).generate_report(
                [make_entry(content="任务")],
                on_chunk=lambda c: received_chunks.append(c),
            )

        assert received_chunks == ["内容"]   # 空 delta 被跳过

    def test_streaming_uses_stream_true_flag(self, tmp_config):
        """流式调用时，OpenAI 请求参数 stream=True 应被传递。"""
        tmp_config.set("api_key", "sk-test")

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter([])

        with patch("src.services.ai_client.OpenAI", return_value=mock_client):
            AIClient(tmp_config).generate_report(
                [make_entry(content="任务")],
                on_chunk=lambda c: None,
            )

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs.get("stream") is True

    def test_streaming_with_no_valid_entries(self, tmp_config):
        """流式调用：0 条有效记录时 prompt 不含无效内容，流正常返回。(ID-07)"""
        tmp_config.set("api_key", "sk-test")
        # 全部 skipped 或空内容
        entries = [
            make_entry(content="", skipped=True),
            make_entry(content="", skipped=False),
        ]
        mock_client = MagicMock()
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "今日无有效记录。"
        mock_client.chat.completions.create.return_value = iter([chunk])

        with patch("src.services.ai_client.OpenAI", return_value=mock_client):
            result = AIClient(tmp_config).generate_report(
                entries, on_chunk=lambda c: None,
            )
        assert result == "今日无有效记录。"

    def test_streaming_with_delta_none_content(self, tmp_config):
        """流式调用：delta.content 为 None (非空串) 时正确跳过。(ID-07)"""
        tmp_config.set("api_key", "sk-test")
        chunk_none = MagicMock()
        chunk_none.choices = [MagicMock()]
        chunk_none.choices[0].delta.content = None  # None, not ""

        chunk_valid = MagicMock()
        chunk_valid.choices = [MagicMock()]
        chunk_valid.choices[0].delta.content = "有效"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter([chunk_none, chunk_valid])

        received = []
        with patch("src.services.ai_client.OpenAI", return_value=mock_client):
            result = AIClient(tmp_config).generate_report(
                [make_entry(content="任务")],
                on_chunk=lambda c: received.append(c),
            )
        assert received == ["有效"]
        assert result == "有效"


# ── FD-02: AI 日报增强 — 待办注入 ─────────────────────────────────────────────

def make_todo(tid=1, title="测试待办", status="pending", note=""):
    return {"id": tid, "title": title, "status": status, "note": note,
            "priority": 1, "due_date": None}


class TestFormatTodoSummary:
    """_format_todo_summary 格式化待办摘要。"""

    def test_empty_todos_returns_empty(self):
        assert _format_todo_summary(None) == ""
        assert _format_todo_summary([]) == ""

    def test_all_done_shows_completed(self):
        todos = [make_todo(1, "A", "done"), make_todo(2, "B", "done")]
        result = _format_todo_summary(todos)
        assert "已完成 2 项" in result
        assert "A" in result
        assert "B" in result
        assert "⬜ 未完成" not in result

    def test_all_pending_shows_pending(self):
        todos = [make_todo(1, "A", "pending"), make_todo(2, "B", "in_progress")]
        result = _format_todo_summary(todos)
        assert "已完成 0 项" in result
        assert "⬜ 未完成" in result
        assert "A" in result
        assert "B" in result


# ── D2: build_prompt period 参数 ────────────────────────────────────────────────

class TestBuildPromptPeriod:
    """build_prompt() period 参数控制周报/月报 Prompt 差异。"""

    def test_daily_uses_today_wording(self):
        entry = make_entry(content="开发")
        prompt = build_prompt([entry], period="daily")
        assert "日期：" in prompt
        assert "今日共完成" in prompt or "共完成" in prompt

    def test_weekly_uses_period_range(self):
        entry = make_entry(content="开发")
        prompt = build_prompt([entry], period="weekly",
                              report_date="2026-06-14")
        assert "周期：" in prompt
        assert "本周共完成" in prompt

    def test_monthly_uses_period_range(self):
        entry = make_entry(content="开发")
        prompt = build_prompt([entry], period="monthly",
                              report_date="2026-06-14")
        assert "周期：" in prompt
        assert "本月共完成" in prompt

    def test_period_defaults_to_daily(self):
        """不传 period 时向后兼容，行为等同 daily。"""
        entry = make_entry(content="开发")
        prompt_default = build_prompt([entry])
        prompt_explicit = build_prompt([entry], period="daily")
        assert prompt_default == prompt_explicit

    def test_weekly_prompt_has_different_structure(self):
        """周报 Prompt 结构与日报不同（含周范围信息）。"""
        entries = [make_entry(session_no=i, content=f"任务{i}")
                   for i in range(1, 4)]
        daily = build_prompt(entries, period="daily")
        weekly = build_prompt(entries, period="weekly",
                              report_date="2026-06-14")
        # 周报包含本周范围
        assert "周" in weekly or "本周" in weekly
        # 日报和周报的统计措辞不同
        assert "今日" in daily or "日期" in daily

    def test_mixed_status_shows_both(self):
        todos = [
            make_todo(1, "已完成", "done"),
            make_todo(2, "未完成", "pending"),
        ]
        result = _format_todo_summary(todos)
        assert "✅ 已完成" in result
        assert "⬜ 未完成" in result
        assert "已完成" in result
        assert "未完成" in result

    def test_todo_with_note_includes_note(self):
        todos = [make_todo(1, "重要任务", "done", note="已完成审查")]
        result = _format_todo_summary(todos)
        assert "已完成审查" in result
        assert "— 已完成审查" in result


class TestBuildPromptWithTodos:
    """build_prompt 包含待办时注入待办摘要 (FD-02)。"""

    def test_todos_none_not_injected(self):
        prompt = build_prompt([make_entry(content="任务")], todos=None)
        assert "待办" not in prompt
        assert "✅" not in prompt

    def test_todos_empty_list_not_injected(self):
        prompt = build_prompt([make_entry(content="任务")], todos=[])
        assert "待办" not in prompt

    def test_todos_injected_in_prompt(self):
        todos = [make_todo(1, "写报告", "done")]
        prompt = build_prompt([make_entry(content="任务")], todos=todos)
        assert "今日待办" in prompt
        assert "已完成 1 项" in prompt
        assert "写报告" in prompt

    def test_todos_with_entries_combined(self):
        """待办摘要和番茄钟记录同时存在。"""
        todos = [make_todo(1, "代码审查", "done")]
        prompt = build_prompt(
            [make_entry(content="完成任务A")],
            "2026年06月14日",
            todos=todos,
        )
        assert "2026年06月14日" in prompt
        assert "番茄钟记录" in prompt
        assert "完成任务A" in prompt
        assert "今日待办" in prompt
        assert "代码审查" in prompt
