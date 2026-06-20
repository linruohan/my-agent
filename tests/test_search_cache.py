from __future__ import annotations

from pathlib import Path

from src.memory.search_cache import (
    SearchCache,
    make_cache_key,
    text_similarity,
    _normalize_query,
)


def test_normalize_strips_search_prefix():
    assert _normalize_query("搜索 Python 3.14 新特性") == "python 3.14 新特性"


def test_make_cache_key_from_search_query():
    assert make_cache_key("Python 3.14 新特性", "搜索 Python 3.14 新特性") == "python 3.14 新特性"


def test_text_similarity_with_prefix():
    score = text_similarity("python 3.14 新特性", "搜索 Python 3.14 新特性")
    assert score >= 0.65


def test_search_cache_lookup_text_match(tmp_path: Path):
    db = tmp_path / "cache.db"
    cache = SearchCache(db_path=db)
    cache.enabled = True
    cache.text_threshold = 0.65
    cache.min_response_chars = 10
    cache.save(
        "搜索 Python 3.14 新特性",
        "Python 3.14 新特性",
        "cached answer " * 5,
        skip_quality=True,
    )
    hit = cache.lookup("python 3.14 新特性")
    assert hit is not None
    assert "cached answer" in hit


def test_search_cache_save_and_reload(tmp_path: Path):
    db = tmp_path / "cache.db"
    cache = SearchCache(db_path=db)
    cache.enabled = True
    cache.min_response_chars = 5
    cache.save("query a", "search a", "answer a long enough", skip_quality=True)

    loaded = SearchCache(db_path=db)
    assert loaded.entry_count == 1
    assert loaded.entries[0].response == "answer a long enough"


def test_search_cache_merges_same_search_query(tmp_path: Path):
    db = tmp_path / "cache.db"
    cache = SearchCache(db_path=db)
    cache.min_response_chars = 5
    cache.save("问法一", "Python 3.14", "response v1 long", skip_quality=True)
    cache.save("问法二", "Python 3.14", "response v2 longer", skip_quality=True)

    loaded = SearchCache(db_path=db)
    assert loaded.entry_count == 1
    assert loaded.entries[0].response == "response v2 longer"
