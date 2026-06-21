"""Agent 消息历史截断。"""

from __future__ import annotations

from typing import Any


def trim_messages_for_model(messages: list[Any], max_messages: int) -> list[Any]:
    """保留最近 max_messages 条消息，控制 LLM 上下文长度。"""
    if max_messages <= 0 or len(messages) <= max_messages:
        return messages
    return list(messages[-max_messages:])


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
