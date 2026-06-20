from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from loguru import logger


@dataclass
class StreamEvent:
    kind: str
    payload: Any = None


@dataclass
class AgentRunner:
    graph: Any
    event_queue: queue.Queue = field(default_factory=queue.Queue)
    _thread: threading.Thread | None = field(default=None, init=False)
    _stop_flag: threading.Event = field(default_factory=threading.Event, init=False)

    def run_async(self, user_input: str, thread_id: str | None = None) -> str:
        """在后台线程执行 Agent，事件写入 event_queue。"""
        thread_id = thread_id or str(uuid.uuid4())
        self._stop_flag.clear()

        def _worker() -> None:
            config = {"configurable": {"thread_id": thread_id}}
            try:
                self.event_queue.put(StreamEvent("start", {"thread_id": thread_id}))
                for chunk in self.graph.stream(
                    {"messages": [{"role": "user", "content": user_input}]},
                    config=config,
                    stream_mode="messages",
                ):
                    if self._stop_flag.is_set():
                        self.event_queue.put(StreamEvent("stopped"))
                        return
                    msg, meta = chunk if isinstance(chunk, tuple) else (chunk, {})
                    self._handle_message(msg, meta)
                self.event_queue.put(StreamEvent("done", {"thread_id": thread_id}))
            except Exception as exc:
                logger.exception("Agent 执行失败")
                self.event_queue.put(StreamEvent("error", str(exc)))

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()
        return thread_id

    def stop(self) -> None:
        self._stop_flag.set()

    def _handle_message(self, msg: Any, meta: dict) -> None:
        if isinstance(msg, (AIMessage, AIMessageChunk)):
            if msg.content:
                self.event_queue.put(StreamEvent("token", str(msg.content)))
            if getattr(msg, "tool_calls", None):
                for tc in msg.tool_calls:
                    self.event_queue.put(
                        StreamEvent(
                            "tool_call",
                            {"name": tc.get("name"), "args": tc.get("args", {})},
                        )
                    )
        elif isinstance(msg, ToolMessage):
            self.event_queue.put(
                StreamEvent(
                    "tool_result",
                    {"name": msg.name, "content": str(msg.content)[:500]},
                )
            )

    def poll_events(self, handler: Callable[[StreamEvent], None]) -> bool:
        """处理队列中所有待处理事件。返回是否仍在运行。"""
        while True:
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break
            handler(event)
            if event.kind in ("done", "error", "stopped"):
                return False
        return self._thread is not None and self._thread.is_alive()
