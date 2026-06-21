"""搜索优先流程：web_search → LLM 汇总。"""

from __future__ import annotations

from typing import Any, Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from src.infra.time_context import current_date_context, current_year
from src.infra.timing import log_timing
from src.tools.tool_worker import invoke_tool_in_process

SummarizeFn = Callable[[str], None]
StatusFn = Callable[[str, str | None], None]


def _extract_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


def _summarize_system_prompt() -> str:
    date_ctx = current_date_context()
    year = current_year()
    return f"""你是个人助理。根据下方【搜索结果】回答用户问题。

【当前时间】今天是 {date_ctx}，当前年份 {year} 年。

【回答规则】
1. 用自然语言汇总：开头直接给出结论，再分点说明要点，附 1–3 个关键来源链接。
2. 禁止原文粘贴或逐条复述搜索摘要，不要出现「【搜索时间】」「【原始查询】」等工具输出格式。
3. 若搜索结果不足或明显过时，如实说明并建议换个关键词。
4. 只输出面向用户的最终回答，不要解释你的推理过程。"""


def search_result_ok(raw: str) -> bool:
    text = (raw or "").strip()
    if not text:
        return False
    bad = ("搜索失败", "未找到", "未返回有效", "工具执行失败", "未知工具")
    return not any(m in text for m in bad)


def run_web_search_turn(
    llm: BaseChatModel,
    user_query: str,
    *,
    on_token: SummarizeFn,
    on_search_status: StatusFn | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[str, str, bool]:
    """执行 web_search 并用 LLM 汇总。返回 (response, raw_search, search_ok)。"""
    query = user_query.strip()
    if not query:
        return "请输入要搜索的内容。", "", False

    with log_timing("search_turn", query=query[:40]):
        if on_search_status:
            on_search_status(f"🔍 正在搜索：{query}", "info")

        raw = invoke_tool_in_process("web_search", {"query": query})
        ok = search_result_ok(raw)

        if cancel_check and cancel_check():
            return "", raw, ok

        if on_search_status:
            if ok:
                on_search_status("✓ 搜索完成，正在汇总…", "success")
            else:
                on_search_status("⚠ 搜索未返回有效结果，正在分析…", "error")

        prompt = f"用户问题：{query}\n\n【搜索结果】\n{raw}"
        messages = [SystemMessage(content=_summarize_system_prompt()), HumanMessage(content=prompt)]

        parts: list[str] = []
        try:
            for chunk in llm.stream(messages):
                if cancel_check and cancel_check():
                    return "".join(parts).strip(), raw, ok
                token = _extract_text(getattr(chunk, "content", chunk))
                if token:
                    parts.append(token)
                    on_token(token)
        except Exception:
            logger.exception("LLM 流式汇总失败，回退 invoke")
            msg = llm.invoke(messages)
            text = _extract_text(getattr(msg, "content", msg))
            if text and not parts:
                on_token(text)
            parts = [text] if text else parts

        response = "".join(parts).strip()
        if not response:
            response = "未能根据搜索结果生成有效回复，请换个关键词重试。"
        return response, raw, ok
