"""Agent 消息历史截断（条数 + token 预算 + 工具结果压缩）。"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import ToolMessage


def _is_tool_message(msg: Any) -> bool:
    return isinstance(msg, ToolMessage)


def _message_text(msg: Any) -> str:
    content = getattr(msg, "content", None)
    if content is None and isinstance(msg, dict):
        content = msg.get("content")
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


def estimate_tokens(text: str) -> int:
    """粗估 token：中文约 1.5 字/token，英文约 4 字符/token。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = max(0, len(text) - cjk)
    return max(1, int(cjk / 1.5 + other / 4) + 1)


def estimate_message_tokens(msg: Any) -> int:
    tokens = estimate_tokens(_message_text(msg))
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        for call in tool_calls:
            if isinstance(call, dict):
                tokens += estimate_tokens(str(call.get("name", "")))
                tokens += estimate_tokens(str(call.get("args", "")))
            else:
                tokens += estimate_tokens(str(getattr(call, "name", "")))
                tokens += estimate_tokens(str(getattr(call, "args", "")))
    return tokens


def compress_tool_results(
    messages: list[Any],
    *,
    max_chars: int,
    keep_recent_tools: int = 4,
) -> list[Any]:
    """压缩较早的 ToolMessage，保留最近若干条完整工具结果。"""
    if max_chars <= 0 or not messages:
        return messages

    tool_indices = [i for i, m in enumerate(messages) if _is_tool_message(m)]
    if not tool_indices:
        return messages

    protect = set(tool_indices[-keep_recent_tools:])
    changed = False
    out = list(messages)
    for idx in tool_indices:
        if idx in protect:
            continue
        msg = out[idx]
        text = _message_text(msg)
        if len(text) <= max_chars:
            continue
        truncated = text[:max_chars].rstrip() + "\n…[工具结果已截断]"
        if isinstance(msg, ToolMessage):
            out[idx] = ToolMessage(
                content=truncated,
                tool_call_id=msg.tool_call_id,
                name=msg.name,
            )
        elif isinstance(msg, dict):
            cloned = dict(msg)
            cloned["content"] = truncated
            out[idx] = cloned
        else:
            continue
        changed = True
    return out if changed else messages


def trim_messages_for_model(
    messages: list[Any],
    max_messages: int,
    *,
    max_tokens: int = 0,
    tool_result_max_chars: int = 0,
) -> list[Any]:
    """保留最近消息：先压工具结果，再按条数，再按 token 预算。"""
    if not messages:
        return messages

    working = messages
    if tool_result_max_chars > 0:
        working = compress_tool_results(working, max_chars=tool_result_max_chars)

    if max_messages > 0 and len(working) > max_messages:
        start = len(working) - max_messages
        while start > 0 and _is_tool_message(working[start]):
            start -= 1
        trimmed = working[start:]
        while trimmed and _is_tool_message(trimmed[0]):
            trimmed = trimmed[1:]
        working = list(trimmed)

    if max_tokens > 0:
        working = _trim_by_token_budget(working, max_tokens)

    return working


def _trim_by_token_budget(messages: list[Any], max_tokens: int) -> list[Any]:
    if max_tokens <= 0 or not messages:
        return messages

    total = 0
    keep_from = len(messages)
    for i in range(len(messages) - 1, -1, -1):
        cost = estimate_message_tokens(messages[i])
        if total + cost > max_tokens and keep_from < len(messages):
            break
        total += cost
        keep_from = i

    if keep_from == 0:
        return messages

    while keep_from < len(messages) and _is_tool_message(messages[keep_from]):
        keep_from += 1

    trimmed = list(messages[keep_from:])
    while trimmed and _is_tool_message(trimmed[0]):
        trimmed = trimmed[1:]
    return trimmed or list(messages[-1:])


def make_pre_model_hook(
    max_messages: int,
    *,
    max_tokens: int = 0,
    tool_result_max_chars: int = 0,
):
    """构建 LangGraph pre_model_hook，在每次模型调用前截断/压缩历史。"""

    if max_messages <= 0 and max_tokens <= 0 and tool_result_max_chars <= 0:
        return None

    def hook(state: dict[str, Any]) -> dict[str, Any]:
        messages = state.get("messages") or []
        trimmed = trim_messages_for_model(
            messages,
            max_messages,
            max_tokens=max_tokens,
            tool_result_max_chars=tool_result_max_chars,
        )
        if trimmed is messages:
            return {}
        return {"messages": trimmed}

    return hook
