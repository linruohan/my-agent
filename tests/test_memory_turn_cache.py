"""相关记忆每用户轮仅检索一次。"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.agent.memory_session import (
    begin_memory_turn,
    clear_memory_conversation_state,
    reset_memory_thread_id,
    set_memory_thread_id,
)
from src.agent.graph import _build_relevant_memories_block
from src.memory.memory_index import MemoryEntry
from src.memory.memory_reader import FoundMemory


def test_relevant_memories_retrieved_once_per_turn(monkeypatch, tmp_path):
    clear_memory_conversation_state()
    token = set_memory_thread_id("thread-perf-1")
    begin_memory_turn("thread-perf-1")
    try:
        entry = MemoryEntry(
            file_name="prefs.md",
            name="prefs",
            description="用户偏好",
            memory_type="user",
            created="2026-01-01",
            updated="2026-01-01",
            tags=[],
            path=tmp_path / "prefs.md",
        )
        monkeypatch.setattr(
            "src.agent.graph.load_all_memory_entries",
            lambda: [entry],
        )
        calls = {"n": 0}

        def fake_find(llm, input_data):
            calls["n"] += 1
            return [
                FoundMemory(file_name="prefs.md", confidence=0.9, reason="hit"),
            ]

        monkeypatch.setattr("src.agent.graph.find_relevant_memories", fake_find)
        monkeypatch.setattr(
            "src.agent.graph.build_memory_injection_block",
            lambda memories: "偏好：简洁",
        )

        state = {"messages": [{"role": "user", "content": "帮我写邮件"}]}
        llm = MagicMock()
        first = _build_relevant_memories_block(llm, state)
        second = _build_relevant_memories_block(llm, state)
        assert "相关记忆" in first
        assert first == second
        assert calls["n"] == 1

        begin_memory_turn("thread-perf-1")
        third = _build_relevant_memories_block(llm, state)
        assert "相关记忆" in third
        assert calls["n"] == 2
    finally:
        reset_memory_thread_id(token)
        clear_memory_conversation_state()
