"""AgentRunner 单元测试：流式事件、HITL 审批与停止。"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from src.agent.runner import AgentRunner, StreamEvent


class _Snapshot:
    def __init__(self, *, next_nodes: tuple[str, ...] = (), values: dict | None = None) -> None:
        self.next = next_nodes
        self.values = values or {}


@dataclass
class MockGraph:
    """模拟 LangGraph：可控 stream / get_state / update_state。"""

    stream_chunks: list[Any] = field(default_factory=list)
    state_sequence: list[_Snapshot] = field(default_factory=list)
    update_state_calls: list[tuple] = field(default_factory=list)
    _stream_call_count: int = 0

    def stream(self, input_data: Any, config: dict | None = None, stream_mode: str = "messages"):
        del config, stream_mode
        self._stream_call_count += 1
        for chunk in self.stream_chunks:
            yield chunk

    def get_state(self, config: dict | None = None) -> _Snapshot:
        del config
        if self.state_sequence:
            return self.state_sequence.pop(0)
        return _Snapshot()

    def update_state(self, config: dict | None, update: dict) -> None:
        self.update_state_calls.append((config, update))


def _collect_events(runner: AgentRunner, timeout: float = 2.0) -> list[StreamEvent]:
    """等待后台线程结束并排空 event_queue。"""
    if runner._thread:
        runner._thread.join(timeout=timeout)
    events: list[StreamEvent] = []
    while True:
        try:
            events.append(runner.event_queue.get_nowait())
        except queue.Empty:
            break
    return events


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (None, ""),
        ("hello", "hello"),
        ([{"text": "a"}, {"content": "b"}], "ab"),
        ([{"other": "x"}], ""),
    ],
)
def test_extract_text(content, expected):
    assert AgentRunner._extract_text(content) == expected


def test_run_async_emits_start_token_done():
    graph = MockGraph(
        stream_chunks=[
            (AIMessageChunk(content="你"), {}),
            (AIMessageChunk(content="好"), {}),
        ],
    )
    runner = AgentRunner(graph=graph)
    runner.run_async("你好", thread_id="t1")
    events = _collect_events(runner)

    kinds = [e.kind for e in events]
    assert kinds[0] == "start"
    assert kinds.count("token") == 2
    assert events[1].payload == "你"
    assert events[2].payload == "好"
    assert kinds[-1] == "done"
    assert events[-1].payload == {"thread_id": "t1"}


def test_run_async_emits_tool_call_and_result():
    graph = MockGraph(
        stream_chunks=[
            (
                AIMessage(
                    content="",
                    tool_calls=[{"name": "list_tasks", "args": {}, "id": "tc1"}],
                ),
                {},
            ),
            (ToolMessage(content="[]", name="list_tasks", tool_call_id="tc1"), {}),
        ],
    )
    runner = AgentRunner(graph=graph)
    runner.run_async("列出任务")
    events = _collect_events(runner)

    tool_call = next(e for e in events if e.kind == "tool_call")
    assert tool_call.payload["name"] == "list_tasks"
    tool_result = next(e for e in events if e.kind == "tool_result")
    assert tool_result.payload["name"] == "list_tasks"


def test_run_async_graph_error_emits_error():
    class FailGraph:
        def stream(self, *args, **kwargs):
            raise RuntimeError("boom")
            yield  # pragma: no cover

    runner = AgentRunner(graph=FailGraph())
    runner.run_async("test")
    events = _collect_events(runner)
    assert any(e.kind == "error" and "boom" in e.payload for e in events)


def test_stop_emits_stopped():
    gate = threading.Event()

    class SlowGraph:
        def stream(self, *args, **kwargs):
            gate.set()
            time.sleep(0.3)
            yield (AIMessageChunk(content="x"), {})

        def get_state(self, config=None):
            return _Snapshot()

    runner = AgentRunner(graph=SlowGraph())
    runner.run_async("slow")
    assert gate.wait(timeout=1.0)
    runner.stop()
    events = _collect_events(runner, timeout=3.0)
    assert any(e.kind == "stopped" for e in events)


@patch("src.agent.runner.needs_user_approval", return_value=True)
@patch("src.agent.runner.format_approval_description", return_value="确认删除？")
def test_hitl_approval_resume(_fmt, _needs):
    resume_input: list[Any] = []

    class HitlGraph:
        def __init__(self) -> None:
            self._phase = 0

        def stream(self, input_data, config=None, stream_mode="messages"):
            resume_input.append(input_data)
            if self._phase == 0:
                self._phase = 1
                yield (
                    AIMessage(
                        content="",
                        tool_calls=[{"name": "delete_path", "args": {"path": "/tmp/x"}, "id": "tc1"}],
                    ),
                    {},
                )
            else:
                yield (AIMessageChunk(content="已删除"), {})

        def get_state(self, config=None):
            if self._phase == 1 and len(resume_input) == 1:
                return _Snapshot(
                    next_nodes=("tools",),
                    values={
                        "messages": [
                            AIMessage(
                                content="",
                                tool_calls=[
                                    {"name": "delete_path", "args": {"path": "/tmp/x"}, "id": "tc1"}
                                ],
                            )
                        ]
                    },
                )
            return _Snapshot()

        def update_state(self, config, update):
            pass

    graph = HitlGraph()
    runner = AgentRunner(graph=graph)
    runner.run_async("删除文件")

    deadline = time.time() + 2.0
    approval_event = None
    while time.time() < deadline:
        try:
            ev = runner.event_queue.get(timeout=0.05)
            if ev.kind == "approval_required":
                approval_event = ev
                break
        except queue.Empty:
            continue
    assert approval_event is not None
    assert approval_event.payload["description"] == "确认删除？"

    runner.resume_after_approval(True)
    events = _collect_events(runner, timeout=3.0)
    assert any(e.kind == "token" and e.payload == "已删除" for e in events)
    assert events[-1].kind == "done"


@patch("src.agent.runner.needs_user_approval", return_value=True)
@patch("src.agent.runner.reject_pending_tools")
def test_hitl_rejection_updates_state(mock_reject, _needs):
    reject_msg = ToolMessage(content="rejected", name="delete_path", tool_call_id="tc1")
    mock_reject.return_value = [reject_msg]

    class RejectGraph:
        def __init__(self) -> None:
            self.last_update: dict | None = None

        def stream(self, input_data, config=None, stream_mode="messages"):
            yield (
                AIMessage(
                    content="",
                    tool_calls=[{"name": "delete_path", "args": {}, "id": "tc1"}],
                ),
                {},
            )

        def get_state(self, config=None):
            return _Snapshot(
                next_nodes=("tools",),
                values={
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[{"name": "delete_path", "args": {}, "id": "tc1"}],
                        )
                    ]
                },
            )

        def update_state(self, config, update):
            self.last_update = update

    graph = RejectGraph()
    runner = AgentRunner(graph=graph)
    runner.run_async("删除")
    _wait_for_approval(runner)
    runner.resume_after_approval(False)
    runner._thread.join(timeout=2.0)
    assert graph.last_update == {"messages": [reject_msg]}


def _wait_for_approval(runner: AgentRunner) -> None:
    deadline = time.time() + 2.0
    while time.time() < deadline:
        try:
            ev = runner.event_queue.get(timeout=0.05)
            if ev.kind == "approval_required":
                return
        except queue.Empty:
            continue
    pytest.fail("未收到 approval_required 事件")


def test_poll_events_drains_queue_and_reports_alive():
    graph = MagicMock()
    runner = AgentRunner(graph=graph)
    runner._thread = threading.Thread(target=lambda: None)
    runner._thread.start()
    runner._thread.join()

    received: list[StreamEvent] = []
    runner.event_queue.put(StreamEvent("token", "a"))
    runner.event_queue.put(StreamEvent("token", "b"))

    still = runner.poll_events(received.append)
    assert still is False
    assert len(received) == 2


def test_poll_events_waits_on_approval():
    graph = MagicMock()
    runner = AgentRunner(graph=graph)
    runner._thread = threading.Thread(target=lambda: time.sleep(0.5))
    runner._thread.start()

    received: list[StreamEvent] = []
    runner.event_queue.put(StreamEvent("approval_required", {"description": "确认？"}))

    still = runner.poll_events(received.append)
    assert still is True
    assert received[0].kind == "approval_required"

    runner._thread.join(timeout=2.0)
