from datetime import date

from openai import OpenAI

from src.services.logger import get_logger

logger = get_logger(__name__)

DEFAULT_SYSTEM_PROMPT = """\
你是一个专业的工作日报助手。请根据用户提供的番茄钟记录，生成一份结构化、专业的工作日报。

要求：
1. 按工作类型分类汇总（如开发、测试、会议、文档等）
2. 提炼关键工作成果，去除重复内容
3. 语言简洁专业
4. 在末尾附上今日工作统计（番茄钟数量、专注时长）
5. 输出 Markdown 格式

注意：跳过或内容为空的记录请忽略。\
"""


def build_prompt(entries: list[dict], report_date: str | None = None) -> str:
    if not report_date:
        report_date = date.today().strftime("%Y年%m月%d日")

    valid = [e for e in entries if not e.get("skipped") and e.get("content")]

    lines = [f"日期：{report_date}", "", "番茄钟记录："]
    for e in valid:
        tags = ", ".join(e.get("tags") or [])
        tag_str = f"[{tags}] " if tags else ""
        lines.append(
            f"- {e['start_time'][:5]}-{e['end_time'][:5]} · {tag_str}{e['content']}"
        )

    lines.append(
        f"\n共完成 {len(valid)} 个番茄钟，约 {len(valid) * 25} 分钟专注工作。"
    )
    return "\n".join(lines)


class AIClient:
    def __init__(self, config):
        self.config = config

    def generate_report(
        self,
        entries: list[dict],
        report_date: str | None = None,
        on_chunk=None,
    ) -> str:
        api_key = self.config.get("api_key", "")
        base_url = self.config.get("api_base_url", "https://api.openai.com/v1")
        model = self.config.get("api_model", "gpt-4o-mini")
        system_prompt = self.config.get("report_system_prompt", "") or DEFAULT_SYSTEM_PROMPT

        local_ollama = str(base_url).startswith("http://localhost:11434") or str(base_url).startswith("http://127.0.0.1:11434")
        if not api_key and not local_ollama:
            raise ValueError("请先在设置中配置 API Key")

        client_kwargs = {"base_url": base_url}
        if api_key:
            client_kwargs["api_key"] = api_key
        client = OpenAI(**client_kwargs)
        prompt = build_prompt(entries, report_date)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        logger.info("AI request: model=%s, entries=%d, date=%s", model, len(entries), report_date)
        try:
            if on_chunk:
                chunks: list[str] = []
                stream = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                    temperature=0.7,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        chunks.append(delta)
                        on_chunk(delta)
                result = "".join(chunks)
                logger.info("AI response received: %d chars", len(result))
                return result

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
            )
            result = response.choices[0].message.content or ""
            logger.info("AI response received: %d chars", len(result))
            return result
        except Exception:
            logger.exception("AI API call failed: model=%s, entries=%d, date=%s", model, len(entries), report_date)
            raise
