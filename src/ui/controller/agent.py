"""Agent 事件轮询与 HITL 审批。"""

from __future__ import annotations

import queue
from typing import Any

from src.agent.runner import StreamEvent


class AgentMixin:
    """LangGraph Agent 事件消费与审批响应。"""

    def approval_response(self, approved: bool) -> None:
        if not self._awaiting_approval:
            return
        self._awaiting_approval = False
        self.runner.resume_after_approval(approved)
        self.chat.append_system("已批准操作，正在执行..." if approved else "已拒绝操作。")

    def _handle_approval(self, payload: dict) -> None:
        if self._awaiting_approval:
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

        skip_until: int | None = None
        for i, event in enumerate(batch):
            if event.kind == "tool_call" and event.payload.get("name") == "web_search":
                skip_until = i
                break

        waiting_approval = False
        still_running = True
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
            return False
        elif event.kind == "stopped":
            self._reset_turn_state()
            self._running = False
            self.chat.set_running(False)
            return False
        return True
