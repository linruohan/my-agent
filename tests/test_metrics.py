"""metrics 持久化与搜索缓存统计测试。"""

from __future__ import annotations

import os

from src.infra.metrics import MetricsStore, metrics_enabled, record_timing
from src.memory.search_cache import SearchCache
from src.memory.search_cache.admin import format_cache_stats, handle_cache_command


def test_metrics_record_and_summarize(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_METRICS", "1")
    store = MetricsStore(tmp_path / "metrics.db")
    for ms in (100, 200, 300, 400, 500):
        store.record_timing("agent_turn", ms, {"thread_id": "abc"})
    summary = store.summarize("agent_turn")
    assert summary["count"] == 5
    assert summary["avg_ms"] == 300
    assert summary["p95_ms"] == 500
    store.close()


def test_record_timing_respects_disable(monkeypatch):
    monkeypatch.setenv("AGENT_METRICS", "0")
    assert metrics_enabled() is False
    record_timing("tool", 10, {"name": "x"})


def test_cache_session_stats(tmp_path):
    cache = SearchCache(db_path=tmp_path / "c.db")
    cache.enabled = True
    cache.text_threshold = 0.65
    cache.min_response_chars = 10
    cache.save("q1", "q1", "answer " * 10, skip_quality=True)

    assert cache.lookup("unknown query") is None
    assert cache.session_stats.misses == 1

    hit = cache.lookup("q1")
    assert hit is not None
    assert cache.session_stats.hits == 1
    assert cache.session_stats.hit_rate == 0.5

    text = format_cache_stats(cache)
    assert "活跃条目" in text
    assert "50.0%" in text or "50%" in text

    stats_cmd = handle_cache_command("stats", cache)
    assert "搜索缓存统计" in stats_cmd
