from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from loguru import logger

from src.tools import get_tool_meta, requires_confirmation


def get_pending_tool_calls(state_values: dict[str, Any]) -> list[dict[str, Any]]:
    messages = state_values.get("messages", [])
    if not messages:
        return []
    last = messages[-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return list(last.tool_calls)
    return []


def needs_user_approval(tool_calls: list[dict[str, Any]]) -> bool:
    return any(requires_confirmation(tc.get("name", "")) for tc in tool_calls)


def format_approval_description(tool_calls: list[dict[str, Any]]) -> str:
    lines = ["Agent 请求执行以下敏感操作，请确认：", ""]
    for tc in tool_calls:
        name = tc.get("name", "unknown")
        args = tc.get("args", {})
        meta = get_tool_meta(name)
        risk = meta.get("risk", "unknown")
        lines.append(f"工具: {name}（风险: {risk}）")
        lines.append(f"参数: {json.dumps(args, ensure_ascii=False, indent=2)}")
        lines.append("")
    return "\n".join(lines)


def reject_pending_tools(state_values: dict[str, Any]) -> list[ToolMessage]:
    """为待执行的工具调用生成拒绝消息。"""
    messages = []
    for tc in get_pending_tool_calls(state_values):
        if requires_confirmation(tc.get("name", "")):
            messages.append(
                ToolMessage(
                    content="用户已拒绝执行此操作。请向用户说明操作未执行，并询问是否需要其他帮助。",
                    tool_call_id=tc.get("id", ""),
                    name=tc.get("name", ""),
                )
            )
    return messages


def is_interrupted_before_tools(snapshot) -> bool:
    if not snapshot or not snapshot.next:
        return False
    return any(node == "tools" for node in snapshot.next)
