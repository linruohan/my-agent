"""Agent 事件轮询与 HITL 审批。"""

from __future__ import annotations

import queue
from typing import Any

from src.agent.hitl import (
    format_remote_approval_prompt,
    gateway_hitl_is_ask,
    gateway_should_auto_approve,
)
from src.agent.runner import StreamEvent
from src.gateway.config import load_gateway_config


class AgentMixin:
    """LangGraph Agent 事件消费与审批响应。"""

    def approval_response(self, approved: bool) -> None:
        if not self._awaiting_approval:
            return
        self._awaiting_approval = False
        self.runner.resume_after_approval(approved)
        self.chat.append_system("已批准操作，正在执行..." if approved else "已拒绝操作。")
        ctx = getattr(self, "_gateway_context", None)
        if ctx and getattr(self, "_gateway", None):
            tip = "已批准，正在执行…" if approved else "已拒绝该操作。"
            self._gateway.deliver_reply(ctx["source"], ctx["chat_id"], tip)

    def _handle_approval(self, payload: dict) -> None:
        if self._awaiting_approval:
            return
        tool_calls = list(payload.get("tool_calls") or [])
        ctx = self._gateway_context
        if ctx:
            policy = load_gateway_config().get("remote_hitl", "auto_reject")
            if gateway_hitl_is_ask(policy):
                self._awaiting_approval = True
                description = payload.get("description", "确认执行敏感操作？")
                prompt = format_remote_approval_prompt(description)
                self.chat.append_system("远程 HITL：已向用户请求确认。")
                self.chat.show_approval(description)
                self._gateway.deliver_reply(ctx["source"], ctx["chat_id"], prompt)
                return
            approved = gateway_should_auto_approve(tool_calls, policy)
            if approved:
                names = ", ".join(str(tc.get("name", "")) for tc in tool_calls)
                self.chat.append_system(f"远程入站：已按策略「{policy}」自动批准：{names}")
            else:
                self.chat.append_system(f"远程入站：按策略「{policy}」已拒绝敏感操作。")
            self.runner.resume_after_approval(approved)
            return
        self._awaiting_approval = True
        description = payload.get("description", "确认执行敏感操作？")
        self.chat.show_approval(description)

    def poll_agent_events(self) -> None:
        if not (self.runner and self.runner.graph):
            return

        batch: list[StreamEvent] = []
        while True:
            try:
                batch.append(self.runner.event_queue.get_nowait())
            except queue.Empty:
                break

        if not batch:
            return

        skip_until: int | None = None
        for i, event in enumerate(batch):
            if event.kind == "tool_call" and event.payload.get("name") == "web_search":
                skip_until = i
                break

        waiting_approval = False
        still_running = True
        with self.chat.ui_batch():
            for i, event in enumerate(batch):
                if skip_until is not None and i < skip_until and event.kind == "token":
                    continue
                if event.kind == "approval_required":
                    waiting_approval = True
                if not self._handle_agent_event(event):
                    still_running = False
                    break

            if still_running:
                if waiting_approval:
                    still_running = True
                else:
                    t = self.runner._thread
                    still_running = t is not None and t.is_alive()
                if not still_running and self._running:
                    self._running = False
                    self.chat.set_running(False)

    def _handle_agent_event(self, event: StreamEvent) -> bool:
        if event.kind == "token":
            self.chat.append_token(event.payload)
        elif event.kind == "tool_call":
            p = event.payload
            self._turn_tool_calls.append({"name": p["name"], "args": p.get("args", {})})
            if p["name"] == "web_search":
                self.chat.reset_assistant_for_tool()
                self._turn_used_web_search = True
                self._turn_search_query = str(p.get("args", {}).get("query", ""))
                self._collecting_assistant = False
            self.chat.append_tool_call(p["name"], p.get("args", {}))
        elif event.kind == "tool_result":
            p = event.payload
            if p["name"] == "web_search":
                raw = str(p.get("content", ""))
                self._turn_search_ok = (
                    "搜索失败" not in raw
                    and "未找到" not in raw
                    and "未返回有效" not in raw
                )
                self._collecting_assistant = True
            self.chat.append_tool_result(p["name"], p["content"])
        elif event.kind == "approval_required":
            self._handle_approval(event.payload)
        elif event.kind == "done":
            response = self.chat.assistant_stream_buffer
            self.chat.end_assistant()
            self._maybe_save_search_cache(response)
            self._running = False
            self.chat.set_running(False)
            self.chat.set_status(self._status_text("就绪"))
            return False
        elif event.kind == "error":
            self.chat.append_error(event.payload)
            self._reset_turn_state()
            self._running = False
            self.chat.set_running(False)
            self._gateway_fail("Agent 执行出错，请稍后重试。")
            return False
        elif event.kind == "stopped":
            self._reset_turn_state()
            self._running = False
            self.chat.set_running(False)
            self._gateway_fail("处理已中断。")
            return False
        return True
