"""聊天输入意图识别：斜杠命令、规则、LLM。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from src.ui.input_compose import extract_inline_urls
from src.ui.message_utils import normalize_user_message

INTENT_OCR = "ocr"
INTENT_LINK = "link_summarize"
INTENT_SEARCH = "search"
INTENT_AGENT = "agent"
INTENT_SLASH_NOTE = "slash_note"
INTENT_SLASH_OCR = "slash_ocr"

_SLASH_RE = re.compile(r"^/(note|ocr|search)\b\s*(.*)$", re.IGNORECASE | re.DOTALL)
_OCR_HINT_RE = re.compile(
    r"识别|提取文字|查看文本|识图|文字识别|图片识别|ocr",
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
    reason: str = ""


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
    match = _SLASH_RE.match(body)
    if not match:
        return None

    cmd = match.group(1).lower()
    args = match.group(2).strip()

    if cmd == "note":
        content = _NOTE_PREFIX_RE.sub("", args).strip() or args.strip()
        return InputIntent(kind=INTENT_SLASH_NOTE, note_content=content, reason="slash:/note")

    if cmd == "ocr":
        return InputIntent(kind=INTENT_SLASH_OCR, reason="slash:/ocr")

    if cmd == "search":
        return InputIntent(
            kind=INTENT_SEARCH,
            search_query=args or body,
            reason="slash:/search",
        )
    return None


def _attachment_flags(attachments: list[dict[str, Any]] | None) -> dict[str, bool]:
    attachments = attachments or []
    return {
        "has_images": any(att.get("type") == "image" for att in attachments),
        "has_files": any(att.get("type") == "file" for att in attachments),
        "has_link_att": any(att.get("type") == "link" for att in attachments),
    }


def classify_intent_rules(text: str, attachments: list[dict[str, Any]] | None) -> InputIntent | None:
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
{{"intent":"ocr|link_summarize|search|agent","reason":"简短原因"}}

意图说明：
- ocr：用户要识别/提取图片中的文字（含「识别」「提取文字」「查看文本」等）
- link_summarize：用户提供了链接 URL，希望抓取页面并按指令提取/总结信息
- search：用户要搜索网络实时信息（新闻、热榜、版本等），且不是针对某个给定链接
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
            ]
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
    ruled = classify_intent_rules(text, attachments)
    if ruled:
        return ruled

    if llm is not None:
        llm_intent = classify_intent_llm(llm, text, attachments)
        if llm_intent:
            return llm_intent

    body = normalize_user_message(text or "")
    flags = _attachment_flags(attachments)
    if not flags["has_images"] and not flags["has_files"] and not flags["has_link_att"] and body:
        return InputIntent(kind=INTENT_SEARCH, search_query=body, reason="fallback:plain_text_search")
    return InputIntent(kind=INTENT_AGENT, reason="fallback:agent")
