from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langgraph.types import Command
from loguru import logger

from src.infra.timing import log_timing

from src.agent.hitl import (
    format_approval_description,
    get_pending_tool_calls,
    is_interrupted_before_tools,
    needs_user_approval,
    reject_pending_tools,
)


_EVENT_QUEUE_MAX_SIZE = 1000


@dataclass
class StreamEvent:
    kind: str
    payload: Any = None


@dataclass
class AgentRunner:
    graph: Any
    event_queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=_EVENT_QUEUE_MAX_SIZE))
    event_notify: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _stop_flag: threading.Event = field(default_factory=threading.Event, init=False)
    _approval_event: threading.Event = field(default_factory=threading.Event, init=False)
    _approval_result: bool = field(default=False, init=False)
    _thread_id: str | None = field(default=None, init=False)
    _config: dict | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def _put_event(self, event: StreamEvent) -> None:
        try:
            self.event_queue.put(event, block=False)
        except queue.Full:
            logger.warning("[runner] 事件队列已满，丢弃事件: {}", event.kind)
        self.event_notify.set()

    def run_async(self, user_input: str, thread_id: str | None = None) -> str:
        """在后台线程执行 Agent，事件写入 event_queue。"""
        self._thread_id = thread_id or str(uuid.uuid4())
        self._config = {"configurable": {"thread_id": self._thread_id}}
        self._stop_flag.clear()
        self._approval_event.clear()

        def _worker() -> None:
            try:
                self._put_event(StreamEvent("start", {"thread_id": self._thread_id}))
                with log_timing("agent_turn", thread_id=self._thread_id[:8]):
                    self._stream_loop({"messages": [{"role": "user", "content": user_input}]})
                self._put_event(StreamEvent("done", {"thread_id": self._thread_id}))
            except Exception as exc:
                logger.exception("Agent 执行失败")
                self._put_event(StreamEvent("error", str(exc)))

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()
        return self._thread_id

    def resume_after_approval(self, approved: bool) -> None:
        """UI 线程在用户确认/拒绝后调用，唤醒 Agent 继续执行。"""
        self._approval_result = approved
        self._approval_event.set()

    def stop(self) -> None:
        self._stop_flag.set()
        self._approval_result = False
        self._approval_event.set()

    def _stream_loop(self, input_data: Any) -> None:
        while True:
            if self._stop_flag.is_set():
                self._put_event(StreamEvent("stopped"))
                return

            for chunk in self.graph.stream(
                input_data,
                config=self._config,
                stream_mode="messages",
            ):
                if self._stop_flag.is_set():
                    self._put_event(StreamEvent("stopped"))
                    return
                msg, meta = chunk if isinstance(chunk, tuple) else (chunk, {})
                self._handle_message(msg, meta)

            snapshot = self.graph.get_state(self._config)
            if not is_interrupted_before_tools(snapshot):
                return

            tool_calls = get_pending_tool_calls(snapshot.values)
            if not tool_calls:
                return

            approved = True
            if needs_user_approval(tool_calls):
                self._put_event(
                    StreamEvent(
                        "approval_required",
                        {
                            "tool_calls": tool_calls,
                            "description": format_approval_description(tool_calls),
                        },
                    )
                )
                self._approval_event.clear()
                self._approval_event.wait()
                if self._stop_flag.is_set():
                    self._put_event(StreamEvent("stopped"))
                    return
                approved = self._approval_result

            if approved:
                input_data = Command(resume=True)
            else:
                reject_msgs = reject_pending_tools(snapshot.values)
                if reject_msgs:
                    self.graph.update_state(self._config, {"messages": reject_msgs})
                input_data = None

    def _handle_message(self, msg: Any, meta: dict) -> None:
        if isinstance(msg, (AIMessage, AIMessageChunk)):
            text = self._extract_text(msg.content)
            if text:
                self._put_event(StreamEvent("token", text))
            if getattr(msg, "tool_calls", None):
                for tc in msg.tool_calls:
                    self._put_event(
                        StreamEvent(
                            "tool_call",
                            {"name": tc.get("name"), "args": tc.get("args", {})},
                        )
                    )
        elif isinstance(msg, ToolMessage):
            self._put_event(
                StreamEvent(
                    "tool_result",
                    {"name": msg.name, "content": str(msg.content)[:500]},
                )
            )

    @staticmethod
    def _extract_text(content: Any) -> str:
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

    def poll_events(self, handler: Callable[[StreamEvent], None]) -> bool:
        """处理队列中所有待处理事件。返回是否仍在运行。"""
        waiting_approval = False
        while True:
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break
            if event.kind == "approval_required":
                waiting_approval = True
            handler(event)
            if event.kind in ("done", "error", "stopped"):
                return False
        if waiting_approval:
            return True
        return self._thread is not None and self._thread.is_alive()
