"""记忆索引写盘防抖测试。"""

from __future__ import annotations

import time

from src.memory import memory_index


def test_schedule_write_memory_index_debounces(tmp_path, monkeypatch):
    calls: list[object] = []

    def fake_write(project_root=None):
        calls.append(project_root)

    monkeypatch.setattr(memory_index, "write_memory_index", fake_write)
    memory_index.flush_memory_index_writes()
    calls.clear()

    memory_index.schedule_write_memory_index(tmp_path, delay=0.15)
    memory_index.schedule_write_memory_index(tmp_path, delay=0.15)
    assert calls == []
    time.sleep(0.35)
    assert len(calls) == 1


def test_flush_memory_index_writes_immediate(tmp_path, monkeypatch):
    calls: list[object] = []

    def fake_write(project_root=None):
        calls.append(project_root)

    monkeypatch.setattr(memory_index, "write_memory_index", fake_write)
    memory_index.flush_memory_index_writes()
    calls.clear()
    memory_index.schedule_write_memory_index(tmp_path, delay=10.0)
    assert calls == []
    memory_index.flush_memory_index_writes()
    assert len(calls) == 1
