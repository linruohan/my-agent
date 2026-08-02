"""httpx 复用、rules/memory 缓存、静态 prompt 缓存相关测试。"""

from __future__ import annotations

from pathlib import Path

from src.infra import http_client
from src.memory import memory_index, rules_loader


def test_shared_http_client_reuses_instance():
    http_client.close_shared_http_client()
    a = http_client.shared_http_client()
    b = http_client.shared_http_client()
    assert a is b
    http_client.close_shared_http_client()


def test_rules_loader_mtime_cache(tmp_path, monkeypatch):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    rule_path = rules_dir / "a.md"
    rule_path.write_text("# A\nmust do\n", encoding="utf-8")

    monkeypatch.setattr(rules_loader, "_rules_dirs", lambda project_root=None: [rules_dir])
    rules_loader.invalidate_rules_cache()

    first = rules_loader.load_rules()
    assert len(first) == 1
    cached_id = id(rules_loader._all_rules_cache)
    second = rules_loader.load_rules()
    assert id(rules_loader._all_rules_cache) == cached_id
    assert second[0].name == first[0].name

    rule_path.write_text("# A\nupdated\n", encoding="utf-8")
    third = rules_loader.load_rules()
    assert id(rules_loader._all_rules_cache) != cached_id
    assert "updated" in third[0].content


def test_memory_entries_mtime_cache(tmp_path, monkeypatch):
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir()
    mem_path = mem_dir / "note.md"
    mem_path.write_text(
        "---\nname: n\ndescription: d\ntype: user\n---\nbody\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(memory_index, "_memory_dirs", lambda project_root=None: [mem_dir])
    memory_index.invalidate_memory_entries_cache()

    first = memory_index.load_all_memory_entries(tmp_path)
    assert len(first) == 1
    key = memory_index._root_key(tmp_path)
    cached_id = id(memory_index._entries_cache[key][1])
    second = memory_index.load_all_memory_entries(tmp_path)
    assert id(memory_index._entries_cache[key][1]) == cached_id
    assert second[0].name == first[0].name

    mem_path.write_text(
        "---\nname: n2\ndescription: d2\ntype: user\n---\nbody\n",
        encoding="utf-8",
    )
    third = memory_index.load_all_memory_entries(tmp_path)
    assert third[0].name == "n2"


def test_static_prompt_cache_hit(monkeypatch):
    from src.agent import graph

    calls = {"n": 0}
    original = graph.build_memory_prompt_block

    def counting_block():
        calls["n"] += 1
        return original()

    monkeypatch.setattr(graph, "build_memory_prompt_block", counting_block)
    monkeypatch.setattr(graph, "build_claude_prompt_block", lambda current_file=None: "")
    monkeypatch.setattr(graph, "build_rules_prompt_block", lambda current_file=None: "")
    monkeypatch.setattr(graph, "build_critical_rules_prompt_block", lambda: "")
    monkeypatch.setattr(graph, "rules_fingerprint", lambda: ("r",))
    monkeypatch.setattr(graph, "memory_entries_fingerprint", lambda: ("m",))
    monkeypatch.setattr(graph, "_context_prompt_fingerprint", lambda current_file: ("c",))
    monkeypatch.setattr(graph, "current_date_context", lambda: "2026-08-01")

    with graph._static_prompt_lock:
        graph._static_prompt_key = None
        graph._static_prompt_value = None

    a = graph._build_static_prompt("base", None)
    b = graph._build_static_prompt("base", None)
    assert a == b
    assert calls["n"] == 1
