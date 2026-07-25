"""记忆抽取队列与测试噪声过滤。"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from src.agent.learning import apply_learning
from src.memory.memory_writer import (
    looks_like_test_artifact,
    schedule_memory_extraction,
    write_structured_memory_note,
)


def test_looks_like_test_artifact_magicmock():
    noise = "<MagicMock name='analyze_turn_for_learning().get()' id='2540142320176'>"
    assert looks_like_test_artifact(noise)
    assert looks_like_test_artifact("unittest.mock.MagicMock")
    assert not looks_like_test_artifact("用户偏好深色主题")


def test_write_structured_memory_rejects_magicmock(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.memory.memory_writer.project_config_dir",
        lambda root=None: tmp_path,
    )
    noise = "<MagicMock name='analyze_turn_for_learning().get()' id='1'>"
    assert write_structured_memory_note(noise, project_root=tmp_path) is None
    assert list((tmp_path / "memory").glob("*.md")) == [] if (tmp_path / "memory").exists() else True


def test_apply_learning_rejects_magicmock_note(tmp_path, monkeypatch):
    monkeypatch.setattr("src.agent.learning_dedupe.memory_note_exists", lambda note: False)
    analysis = {
        "save_skill": False,
        "memory_note": MagicMock(name="analyze_turn_for_learning().get()"),
    }
    msg = apply_learning(analysis, auto_create_skill=False, auto_update_memory=True)
    assert msg is None


def test_schedule_memory_extraction_coalesce(monkeypatch):
    calls: list[str] = []
    busy_gate = {"hold": True}

    def fake_extract(llm, input_data, project_root=None):
        while busy_gate["hold"]:
            time.sleep(0.01)
        calls.append(input_data.conversation_id)
        return MagicMock(memories_written=[])

    monkeypatch.setattr(
        "src.memory.memory_writer.memory_extraction_config",
        lambda: {"enabled": True, "min_interval_sec": 0, "provider": "", "coalesce": True},
    )
    monkeypatch.setattr("src.memory.memory_writer.extract_memories", fake_extract)
    monkeypatch.setattr("src.memory.memory_writer.get_last_memory_write_ts", lambda: 0.0)
    monkeypatch.setattr(
        "src.memory.memory_writer.resolve_extraction_llm",
        lambda fallback: fallback,
    )

    def make_graph(thread_id: str):
        graph = MagicMock()
        snapshot = MagicMock()
        snapshot.values = {"messages": [{"role": "user", "content": f"hi-{thread_id}"}]}
        graph.get_state.return_value = snapshot
        return graph

    llm = MagicMock()
    schedule_memory_extraction(
        llm=llm,
        graph=make_graph("t1"),
        thread_id="t1",
        config={"configurable": {"thread_id": "t1"}},
    )
    time.sleep(0.05)
    schedule_memory_extraction(
        llm=llm,
        graph=make_graph("t2"),
        thread_id="t2",
        config={"configurable": {"thread_id": "t2"}},
    )
    schedule_memory_extraction(
        llm=llm,
        graph=make_graph("t3"),
        thread_id="t3",
        config={"configurable": {"thread_id": "t3"}},
    )

    busy_gate["hold"] = False
    deadline = time.time() + 2.0
    while time.time() < deadline and len(calls) < 2:
        time.sleep(0.02)

    # 第一轮 t1 + coalesce 后只跑最新 t3
    assert calls[0] == "t1"
    assert "t3" in calls
    assert "t2" not in calls
