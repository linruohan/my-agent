"""定时任务同步执行 Agent（自动拒绝 HITL 写操作）。"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langgraph.types import Command
from loguru import logger

from src.agent.hitl import (
    get_pending_tool_calls,
    is_interrupted_before_tools,
    needs_user_approval,
    reject_pending_tools,
)


def run_agent_sync(graph: Any, prompt: str, thread_id: str) -> str:
    """无 UI 同步运行 Agent，遇敏感工具自动拒绝并继续。"""
    config = {"configurable": {"thread_id": thread_id}}
    input_data: Any = {"messages": [{"role": "user", "content": prompt}]}
    parts: list[str] = []

    for _ in range(40):
        for chunk in graph.stream(input_data, config=config, stream_mode="messages"):
            msg, _meta = chunk if isinstance(chunk, tuple) else (chunk, {})
            if isinstance(msg, (AIMessage, AIMessageChunk)):
                text = _extract_text(msg.content)
                if text:
                    parts.append(text)
            elif isinstance(msg, ToolMessage):
                parts.append(f"\n[工具 {msg.name}] {str(msg.content)[:300]}\n")

        snapshot = graph.get_state(config)
        if not is_interrupted_before_tools(snapshot):
            break

        tool_calls = get_pending_tool_calls(snapshot.values)
        if not tool_calls:
            break

        if needs_user_approval(tool_calls):
            logger.info("定时任务自动拒绝敏感工具: {}", [tc.get("name") for tc in tool_calls])
            reject_msgs = reject_pending_tools(snapshot.values)
            if reject_msgs:
                graph.update_state(config, {"messages": reject_msgs})
            input_data = None
            continue

        input_data = Command(resume=True)

    return "".join(parts).strip() or "（Agent 无输出）"


def _extract_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for block in content:
            if isinstance(block, dict):
                out.append(str(block.get("text") or block.get("content") or ""))
            else:
                out.append(str(block))
        return "".join(out)
    return str(content)
