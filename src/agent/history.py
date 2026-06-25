"""Agent 消息历史截断。"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import ToolMessage


def _is_tool_message(msg: Any) -> bool:
    return isinstance(msg, ToolMessage)


def trim_messages_for_model(messages: list[Any], max_messages: int) -> list[Any]:
    """保留最近 max_messages 条消息，且不截断 ToolMessage 与 AIMessage 工具链。"""
    if max_messages <= 0 or len(messages) <= max_messages:
        return messages

    start = len(messages) - max_messages
    while start > 0 and _is_tool_message(messages[start]):
        start -= 1

    trimmed = messages[start:]
    while trimmed and _is_tool_message(trimmed[0]):
        trimmed = trimmed[1:]

    return list(trimmed)


def make_pre_model_hook(max_messages: int):
    """构建 LangGraph pre_model_hook，在每次模型调用前截断历史。"""

    if max_messages <= 0:
        return None

    def hook(state: dict[str, Any]) -> dict[str, Any]:
        messages = state.get("messages") or []
        trimmed = trim_messages_for_model(messages, max_messages)
        if len(trimmed) == len(messages):
            return {}
        return {"messages": trimmed}

    return hook
