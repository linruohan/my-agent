"""聊天输入意图识别：斜杠命令、规则、LLM。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from src.tools.weather import (
    WeatherRange,
    detect_weather_range,
    parse_weather_slash_args,
)
from src.ui.input.compose import extract_inline_urls
from src.ui.message_utils import normalize_user_message
from src.ui.skill.catalog import build_slash_catalog

INTENT_OCR = "ocr"
INTENT_LINK = "link_summarize"
INTENT_SEARCH = "search"
INTENT_AGENT = "agent"
INTENT_SLASH_NOTE = "slash_note"
INTENT_SLASH_OCR = "slash_ocr"
INTENT_WEATHER = "weather"
INTENT_SLASH_WEATHER = "slash_weather"
INTENT_SLASH_CACHE = "slash_cache"
INTENT_SLASH_METRICS = "slash_metrics"
INTENT_SLASH_RELOAD = "slash_reload"
INTENT_SLASH_TASK = "slash_task"
INTENT_SLASH_SKILL = "slash_skill"
INTENT_SLASH_FILE = "slash_file"

_SYSTEM_SLASH = {"note", "ocr", "search", "weather", "cache", "metrics", "reload", "tsk", "file"}
_SLASH_GENERIC_RE = re.compile(r"^/([\w-]+)\b\s*(.*)$", re.IGNORECASE | re.DOTALL)
_OCR_HINT_RE = re.compile(
    r"识别|提取文字|查看文本|识图|文字识别|图片识别|ocr",
    re.IGNORECASE,
)
_WEATHER_HINT_RE = re.compile(
    r"^(?:/)?weather\b|(?:查(?:询|看)?|获取|看看)?(?:一下)?天气(?:预报)?(?:怎么样|如何)?[？?]?$",
    re.IGNORECASE,
)
_NOTE_PREFIX_RE = re.compile(r"^(?:添加笔记|新建笔记|笔记)[：:\s]*", re.IGNORECASE)


@dataclass
class InputIntent:
    kind: str
    search_query: str = ""
    urls: list[str] = field(default_factory=list)
    link_instruction: str = ""
    note_content: str = ""
    slash_cmd: str = ""
    slash_args: str = ""
    skill_name: str = ""
    weather_city_code: str = ""
    weather_range: WeatherRange = "7d"
    reason: str = ""


def _skill_names() -> set[str]:
    return {
        s["name"].lower() for s in build_slash_catalog() if s.get("kind") == "skill"
    }


def extract_link_instruction(text: str, urls: list[str]) -> str:
    remainder = text or ""
    for url in urls:
        remainder = remainder.replace(url, " ")
    instruction = normalize_user_message(remainder).strip()
    return instruction or "总结页面主要内容"


def parse_slash_command(text: str) -> InputIntent | None:
    body = normalize_user_message(text or "").strip()
    if not body.startswith("/"):
        return None
    match = _SLASH_GENERIC_RE.match(body)
    if not match:
        return None

    cmd = match.group(1).lower()
    args = match.group(2).strip()

    if cmd == "note":
        if args.lower().startswith(("add ", "list", "rm ")) or args.isdigit():
            return InputIntent(
                kind=INTENT_SLASH_NOTE,
                slash_cmd="note",
                slash_args=args,
                reason="slash:/note",
            )
        content = _NOTE_PREFIX_RE.sub("", args).strip() or args.strip()
        return InputIntent(
            kind=INTENT_SLASH_NOTE,
            slash_cmd="note",
            slash_args=args,
            note_content=content,
            reason="slash:/note",
        )

    if cmd == "ocr":
        return InputIntent(kind=INTENT_SLASH_OCR, slash_cmd="ocr", reason="slash:/ocr")

    if cmd == "search":
        return InputIntent(
            kind=INTENT_SEARCH,
            search_query=args.strip(),
            slash_cmd="search",
            reason="slash:/search",
        )

    if cmd == "weather":
        code, range_type = parse_weather_slash_args(args)
        return InputIntent(
            kind=INTENT_SLASH_WEATHER,
            weather_city_code=code,
            weather_range=range_type,
            slash_cmd="weather",
            reason="slash:/weather",
        )

    if cmd == "cache":
        return InputIntent(
            kind=INTENT_SLASH_CACHE,
            slash_cmd="cache",
            slash_args=args,
            reason="slash:/cache",
        )

    if cmd == "metrics":
        return InputIntent(
            kind=INTENT_SLASH_METRICS,
            slash_cmd="metrics",
            slash_args=args,
            reason="slash:/metrics",
        )

    if cmd == "reload":
        return InputIntent(
            kind=INTENT_SLASH_RELOAD,
            slash_cmd="reload",
            slash_args=args,
            reason="slash:/reload",
        )

    if cmd == "tsk":
        return InputIntent(
            kind=INTENT_SLASH_TASK,
            slash_cmd="tsk",
            slash_args=args,
            reason="slash:/tsk",
        )

    if cmd == "file":
        return InputIntent(
            kind=INTENT_SLASH_FILE,
            slash_cmd="file",
            slash_args=args,
            reason="slash:/file",
        )

    if cmd in _skill_names():
        return InputIntent(
            kind=INTENT_SLASH_SKILL,
            slash_cmd=cmd,
            slash_args=args,
            skill_name=cmd,
            reason=f"slash:/{cmd}",
        )

    return None


def classify_intent_rules(
    text: str,
    attachments: list[dict[str, Any]] | None,
) -> InputIntent | None:
    slash = parse_slash_command(text)
    if slash:
        return slash

    flags = _attachment_flags(attachments)
    body = normalize_user_message(text or "")
    urls = list(extract_inline_urls(body))
    if flags["has_link_att"]:
        for att in attachments or []:
            if att.get("type") == "link":
                url = str(att.get("url", "")).strip()
                if url and url not in urls:
                    urls.append(url)

    if flags["has_images"] and (not body.strip() or _OCR_HINT_RE.search(body)):
        return InputIntent(kind=INTENT_OCR, reason="rule:ocr_keywords_or_empty")

    if not attachments and _is_weather_request(body):
        return InputIntent(
            kind=INTENT_WEATHER,
            weather_range=detect_weather_range(body),
            reason="rule:weather_keyword",
        )

    if urls and not flags["has_files"]:
        return InputIntent(
            kind=INTENT_LINK,
            urls=urls,
            link_instruction=extract_link_instruction(body, urls),
            reason="rule:url_with_text",
        )

    if flags["has_files"]:
        return InputIntent(kind=INTENT_AGENT, reason="rule:file_attachment")

    return None


def _is_weather_request(text: str) -> bool:
    body = normalize_user_message(text or "").strip()
    if not body:
        return False
    if _WEATHER_HINT_RE.search(body):
        return True
    if re.search(r"天气(?:预报)?", body, re.IGNORECASE) and len(body) <= 24:
        return True
    return False


def _attachment_flags(attachments: list[dict[str, Any]] | None) -> dict[str, bool]:
    attachments = attachments or []
    return {
        "has_images": any(att.get("type") == "image" for att in attachments),
        "has_files": any(att.get("type") == "file" for att in attachments),
        "has_link_att": any(att.get("type") == "link" for att in attachments),
    }


def _parse_llm_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {}


def _llm_intent_prompt(text: str, attachments: list[dict[str, Any]] | None) -> str:
    flags = _attachment_flags(attachments)
    urls = extract_inline_urls(text)
    return f"""分析用户输入，只返回 JSON（不要 markdown）：
{{"intent":"ocr|link_summarize|search|weather|agent","reason":"简短原因"}}

意图说明：
- ocr：用户要识别/提取图片中的文字（含「识别」「提取文字」「查看文本」等）
- link_summarize：用户提供了链接 URL，希望抓取页面并按指令提取/总结信息
- search：用户要搜索网络实时信息（新闻、热榜、版本等），且不是针对某个给定链接
- weather：用户要查询天气预报（如「天气」「天气预报」「/weather」）
- agent：一般对话、代码、文件、待办、知识库问答等

输入上下文：
- 文本：{text[:800] or "（空）"}
- 含图片：{flags["has_images"]}
- 含文件：{flags["has_files"]}
- 含链接附件：{flags["has_link_att"]}
- 文本内 URL：{urls[:3] if urls else []}
"""


def classify_intent_llm(
    llm: BaseChatModel,
    text: str,
    attachments: list[dict[str, Any]] | None,
) -> InputIntent | None:
    body = normalize_user_message(text or "")
    try:
        msg = llm.invoke(
            [
                SystemMessage(content="你是输入意图分类器，只输出 JSON。"),
                HumanMessage(content=_llm_intent_prompt(body, attachments)),
            ],
        )
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        data = _parse_llm_json(content)
        kind = str(data.get("intent", "")).strip().lower()
        reason = str(data.get("reason", "")).strip() or "llm"

        if kind == INTENT_OCR:
            return InputIntent(kind=INTENT_OCR, reason=reason)
        if kind == INTENT_LINK:
            urls = list(extract_inline_urls(body))
            for att in attachments or []:
                if att.get("type") == "link":
                    url = str(att.get("url", "")).strip()
                    if url and url not in urls:
                        urls.append(url)
            if not urls:
                return InputIntent(kind=INTENT_SEARCH, search_query=body, reason=reason)
            return InputIntent(
                kind=INTENT_LINK,
                urls=urls,
                link_instruction=extract_link_instruction(body, urls),
                reason=reason,
            )
        if kind == INTENT_SEARCH:
            return InputIntent(kind=INTENT_SEARCH, search_query=body, reason=reason)
        if kind == INTENT_WEATHER:
            return InputIntent(kind=INTENT_WEATHER, reason=reason)
        if kind == INTENT_AGENT:
            return InputIntent(kind=INTENT_AGENT, reason=reason)
    except Exception:
        logger.exception("LLM 意图识别失败")
    return None


def resolve_input_intent(
    text: str,
    attachments: list[dict[str, Any]] | None,
    *,
    llm: BaseChatModel | None = None,
) -> InputIntent:
    """识别斜杠命令与规则意图；其余交给路由层（缓存 → Agent）。"""
    del llm  # 不再用 LLM 做 search/agent 分流
    ruled = classify_intent_rules(text, attachments)
    if ruled:
        return ruled

    return InputIntent(kind=INTENT_AGENT, reason="fallback:agent")
