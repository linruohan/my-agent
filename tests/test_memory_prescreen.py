"""记忆规则预筛测试。"""

from __future__ import annotations

from pathlib import Path

from src.memory.memory_index import MemoryEntry
from src.memory.memory_reader import _rule_prescreen_memories, clear_memory_selection_cache, find_relevant_memories


def _entry(name: str, desc: str, tags: list[str] | None = None) -> MemoryEntry:
    return MemoryEntry(
        file_name=f"feedback-{name}.md",
        name=name,
        description=desc,
        memory_type="feedback",
        created="2026-07-01",
        updated="2026-07-01",
        tags=tags or [],
        path=Path(f"/tmp/{name}.md"),
    )


def test_rule_prescreen_skips_llm_on_strong_match():
    clear_memory_selection_cache()
    entries = [
        _entry("no-mock", "集成测试不要用 mock，必须连真实数据库", ["测试", "mock"]),
        _entry("theme", "用户喜欢深色主题", ["ui"]),
    ]
    found = _rule_prescreen_memories("集成测试不要用 mock 数据库", entries, 3)
    assert found
    assert found[0].file_name == "feedback-no-mock.md"
    assert found[0].confidence >= 0.55


def test_find_relevant_uses_prescreen_without_llm():
    clear_memory_selection_cache()
    from src.memory.memory_reader import FindRelevantMemoriesInput

    class BoomLLM:
        def invoke(self, *_a, **_k):
            raise AssertionError("高置信预筛不应调用 LLM")

    entries = [
        _entry("no-mock", "集成测试不要用 mock，必须连真实数据库", ["测试"]),
    ]
    out = find_relevant_memories(
        BoomLLM(),
        FindRelevantMemoriesInput(
            query="集成测试不要用 mock",
            memory_files=entries,
            already_surfaced=[],
            recent_tools=[],
            max_results=3,
        ),
    )
    assert out
    assert out[0].file_name == "feedback-no-mock.md"
