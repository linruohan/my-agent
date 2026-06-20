"""链接抓取 + LLM 按用户意图提取/总结。"""

from __future__ import annotations

import re
from typing import Any, Callable
from urllib.parse import urlparse

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from src.tools.tool_worker import invoke_tool_in_process
from src.ui.link_fetch_worker import summarize_url_in_process
from src.ui.search_turn import _extract_text, search_result_ok

SummarizeFn = Callable[[str], None]
StatusFn = Callable[[str, str | None], None]

_LIVE_DATA_HINT = re.compile(
    r"热榜|排行榜|榜单|前\s*\d+\s*条|最新|今日|头条|实时",
    re.IGNORECASE,
)


def _summarize_system_prompt() -> str:
    return """你是个人助理。用户提供了一个网页链接和具体指令，请根据【页面内容】完成用户要求。

规则：
1. 严格依据页面内容作答，不要编造页面中不存在的信息。
2. 若页面是动态加载、需登录或内容不足以完成指令，如实说明并给出可行建议。
3. 用清晰的中文结构化输出；若用户要求列表/前 N 条，尽量逐条列出。
4. 不要输出「【页面内容】」等标签，不要描述你的推理过程。
5. 若提供了【网页搜索补充】，可结合搜索结果作答；页面与搜索冲突时说明差异。"""


def _needs_live_supplement(instruction: str, fetched: dict[str, Any]) -> bool:
    if not fetched.get("ok"):
        return True
    if fetched.get("sparse"):
        return True
    if _LIVE_DATA_HINT.search(instruction or ""):
        return _is_sparse_fetch(fetched)
    return False


def _is_sparse_fetch(fetched: dict[str, Any]) -> bool:
    if fetched.get("sparse"):
        return True
    summary = str(fetched.get("summary", ""))
    return len(re.sub(r"\s+", "", summary)) < 280


def _build_search_query(instruction: str, url: str) -> str:
    base = (instruction or "").strip()
    if base:
        return base
    return f"site:{urlparse(url).netloc} 最新内容"


def _fetch_web_supplement(query: str) -> str:
    raw = invoke_tool_in_process("web_search", {"query": query})
    if search_result_ok(raw):
        return raw
    return raw or "搜索未返回有效结果"


def run_link_summarize_turn(
    llm: BaseChatModel,
    instruction: str,
    urls: list[str],
    *,
    on_token: SummarizeFn,
    on_status: StatusFn | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """抓取链接并由 LLM 按指令总结。返回 (response, fetch_results)。"""
    instruction = (instruction or "总结页面主要内容").strip()
    urls = [u.strip() for u in urls if u and u.strip()]
    if not urls:
        return "未找到有效链接。", []

    page_blocks: list[str] = []
    fetch_results: list[dict[str, Any]] = []

    for url in urls:
        if cancel_check and cancel_check():
            return "", fetch_results
        if on_status:
            on_status(f"🔗 正在获取页面：{url}", "info")
        fetched = summarize_url_in_process(url)
        fetch_results.append({"url": url, **fetched})
        if not fetched.get("ok"):
            page_blocks.append(f"### {url}\n抓取失败：{fetched.get('error', '未知错误')}")
            continue
        summary = str(fetched.get("summary", "")).strip()
        engine = fetched.get("engine", "")
        warning = str(fetched.get("warning", "") or "").strip()
        note = str(fetched.get("note", "") or "").strip()
        meta = f"（抓取方式: {engine}，约 {fetched.get('char_count', len(summary))} 字）"
        if warning:
            meta += f"\n⚠ {warning}"
        if note:
            meta += f"\nℹ {note}"
        page_blocks.append(f"### {url}\n{meta}\n\n{summary}")

        if _needs_live_supplement(instruction, fetched):
            if on_status:
                on_status("⚠ 页面内容不足，正在网页搜索补充…", "info")
            search_q = _build_search_query(instruction, url)
            supplement = _fetch_web_supplement(search_q)
            page_blocks.append(f"### 网页搜索补充（{search_q}）\n{supplement}")

    if cancel_check and cancel_check():
        return "", fetch_results

    if on_status:
        on_status("✓ 页面获取完成，正在分析…", "success")

    pages_text = "\n\n---\n\n".join(page_blocks)
    prompt = f"用户指令：{instruction}\n\n【页面内容】\n{pages_text}"
    messages = [SystemMessage(content=_summarize_system_prompt()), HumanMessage(content=prompt)]

    parts: list[str] = []
    try:
        for chunk in llm.stream(messages):
            if cancel_check and cancel_check():
                return "".join(parts).strip(), fetch_results
            token = _extract_text(getattr(chunk, "content", chunk))
            if token:
                parts.append(token)
                on_token(token)
    except Exception:
        logger.exception("链接总结流式失败，回退 invoke")
        msg = llm.invoke(messages)
        text = _extract_text(getattr(msg, "content", msg))
        if text and not parts:
            on_token(text)
        parts = [text] if text else parts

    response = "".join(parts).strip()
    if not response:
        response = "未能根据页面内容生成有效回复，请检查链接是否可访问或换个问法。"
    return response, fetch_results
