from __future__ import annotations

from pathlib import Path

from src.memory.search_cache_db import SearchCacheStore


def test_sqlite_store_upsert_and_list(tmp_path: Path):
    store = SearchCacheStore(tmp_path / "test.db")
    store.upsert(
        cache_key="python 3.14",
        search_query="Python 3.14",
        response="answer",
        user_query="搜索 python 3.14",
        search_ok=True,
        ttl_days=7,
        max_user_queries=5,
    )
    rows = store.list_active()
    assert len(rows) == 1
    assert rows[0].cache_key == "python 3.14"
    assert "搜索 python 3.14" in rows[0].user_queries

    store.record_hit("python 3.14")
    rows = store.list_active()
    assert rows[0].hit_count == 1
