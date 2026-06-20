from __future__ import annotations

from pathlib import Path

from src.memory.search_cache import (
    SearchCache,
    SearchCacheEntry,
    text_similarity,
    _normalize_query,
)


def test_normalize_strips_search_prefix():
    assert _normalize_query("搜索 Python 3.14 新特性") == "python 3.14 新特性"


def test_text_similarity_with_prefix():
    score = text_similarity("python 3.14 新特性", "搜索 Python 3.14 新特性")
    assert score >= 0.65


def test_search_cache_lookup_text_match(tmp_path: Path):
    cache = SearchCache(path=tmp_path / "cache.json")
    cache.enabled = True
    cache.text_threshold = 0.65
    cache.entries = [
        SearchCacheEntry(
            user_query="搜索 Python 3.14 新特性",
            search_query="Python 3.14 新特性",
            response="cached answer",
        )
    ]
    hit = cache.lookup("python 3.14 新特性")
    assert hit == "cached answer"


def test_search_cache_save_and_reload(tmp_path: Path):
    path = tmp_path / "cache.json"
    cache = SearchCache(path=path)
    cache.enabled = True
    cache.save("query a", "search a", "answer a")

    loaded = SearchCache(path=path)
    assert len(loaded.entries) == 1
    assert loaded.entries[0].response == "answer a"
