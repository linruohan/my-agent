from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import interrupt

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


_APPROVE_REPLIES = frozenset({
    "/approve",
    "approve",
    "yes",
    "y",
    "ok",
    "批准",
    "同意",
    "确认",
    "是",
})
_REJECT_REPLIES = frozenset({
    "/reject",
    "reject",
    "no",
    "n",
    "拒绝",
    "否",
    "取消",
})


def gateway_hitl_is_ask(policy: str) -> bool:
    """是否要求远程用户交互确认。"""
    return (policy or "").strip().lower() in ("ask", "interactive")


def parse_remote_approval_reply(text: str) -> bool | None:
    """解析远程批准/拒绝回复。True=批准，False=拒绝，None=非确认指令。"""
    raw = (text or "").strip()
    if not raw:
        return None
    key = raw.lower()
    # 允许 "/approve 原因" 形式
    first = key.split(None, 1)[0]
    if first in _APPROVE_REPLIES or key in _APPROVE_REPLIES:
        return True
    if first in _REJECT_REPLIES or key in _REJECT_REPLIES:
        return False
    if raw in _APPROVE_REPLIES:
        return True
    if raw in _REJECT_REPLIES:
        return False
    return None


def format_remote_approval_prompt(description: str) -> str:
    body = (description or "确认执行敏感操作？").strip()
    return (
        f"{body}\n\n"
        "请回复以下之一：\n"
        "- `/approve` 或「批准」→ 执行\n"
        "- `/reject` 或「拒绝」→ 取消"
    )


def gateway_should_auto_approve(tool_calls: list[dict[str, Any]], policy: str) -> bool:
    """远程 Gateway HITL 策略：True=自动批准，False=自动拒绝。

    ask / interactive 不走自动决策（由调用方交互确认）。
    """
    policy = (policy or "auto_reject").strip().lower()
    if gateway_hitl_is_ask(policy):
        return False
    if policy == "auto_reject":
        return False
    if not tool_calls:
        return True
    risks = [get_tool_meta(tc.get("name", "")).get("risk", "unknown") for tc in tool_calls]
    if policy == "approve_low":
        return all(r == "low" for r in risks)
    if policy == "approve_medium":
        return all(r in ("low", "medium") for r in risks)
    return False


def reject_pending_tools(state_values: dict[str, Any]) -> list[ToolMessage]:
    """为待执行的敏感工具调用生成拒绝消息。"""
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
    """兼容旧 interrupt_before=['tools'] 检测。"""
    if not snapshot or not snapshot.next:
        return False
    return any(node == "tools" for node in snapshot.next)


def get_hitl_interrupt_payload(snapshot) -> dict[str, Any] | None:
    """从 checkpoint 读取 post_model_hook 的 interrupt() 载荷。"""
    if not snapshot:
        return None
    interrupts = getattr(snapshot, "interrupts", None) or ()
    for intr in interrupts:
        value = getattr(intr, "value", None)
        if isinstance(value, dict) and "tool_calls" in value:
            return value
    for task in getattr(snapshot, "tasks", ()) or ():
        for intr in getattr(task, "interrupts", ()) or ():
            value = getattr(intr, "value", None)
            if isinstance(value, dict) and "tool_calls" in value:
                return value
    return None


def is_hitl_interrupted(snapshot) -> bool:
    """是否因敏感工具审批或旧版 tools 节点中断而暂停。"""
    if get_hitl_interrupt_payload(snapshot) is not None:
        return True
    return is_interrupted_before_tools(snapshot)


def make_hitl_post_model_hook():
    """仅在需要确认的工具调用前 interrupt，低风险工具零中断开销。"""

    def hook(state: dict[str, Any]) -> dict[str, Any]:
        tool_calls = get_pending_tool_calls(state)
        if not tool_calls or not needs_user_approval(tool_calls):
            return {}

        payload = {
            "tool_calls": tool_calls,
            "description": format_approval_description(tool_calls),
        }
        approved = interrupt(payload)
        if approved:
            return {}
        return {"messages": reject_pending_tools(state)}

    return hook
