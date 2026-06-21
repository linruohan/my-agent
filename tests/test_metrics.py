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


def test_metrics_export_csv(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_METRICS", "1")
    store = MetricsStore(tmp_path / "metrics.db")
    store.record_timing("tool", 42, {"name": "list_tasks"})
    out = tmp_path / "out.csv"
    n = store.export_csv(out)
    assert n == 1
    text = out.read_text(encoding="utf-8-sig")
    assert "tool" in text
    assert "42" in text
    store.close()


def test_export_metrics_csv_helper(tmp_path, monkeypatch):
    from src.infra.metrics import close_metrics_store, export_metrics_csv, get_metrics_store

    close_metrics_store()
    monkeypatch.setenv("AGENT_METRICS", "1")
    monkeypatch.setattr("src.infra.metrics.DATA_DIR", tmp_path)
    get_metrics_store().record_timing("search_turn", 100)
    count, path = export_metrics_csv(tmp_path / "export.csv")
    assert count == 1
    assert path.exists()
    close_metrics_store()


def test_cache_export_command(tmp_path, monkeypatch):
    from src.infra.metrics import close_metrics_store, get_metrics_store

    close_metrics_store()
    monkeypatch.setenv("AGENT_METRICS", "1")
    monkeypatch.setattr("src.infra.metrics.DATA_DIR", tmp_path)
    get_metrics_store().record_timing("agent_turn", 200)
    cache = SearchCache(db_path=tmp_path / "c.db")
    msg = handle_cache_command("export", cache)
    assert "已导出" in msg
    assert (tmp_path / "metrics_export.csv").exists()
    close_metrics_store()


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
    assert "/metrics" in text

    stats_cmd = handle_cache_command("stats", cache)
    assert "搜索缓存统计" in stats_cmd


def test_metrics_command_stats(tmp_path, monkeypatch):
    from src.infra.metrics import close_metrics_store, get_metrics_store
    from src.infra.metrics_admin import handle_metrics_command

    close_metrics_store()
    monkeypatch.setenv("AGENT_METRICS", "1")
    monkeypatch.setattr("src.infra.metrics.DATA_DIR", tmp_path)
    get_metrics_store().record_timing("agent_turn", 150)
    text = handle_metrics_command("stats")
    assert "agent_turn" in text
    assert "150" in text
    close_metrics_store()


def test_metrics_command_export(tmp_path, monkeypatch):
    from src.infra.metrics import close_metrics_store, get_metrics_store
    from src.infra.metrics_admin import handle_metrics_command

    close_metrics_store()
    monkeypatch.setenv("AGENT_METRICS", "1")
    monkeypatch.setattr("src.infra.metrics.DATA_DIR", tmp_path)
    get_metrics_store().record_timing("tool", 42, {"name": "list_tasks"})
    msg = handle_metrics_command(f"export {tmp_path / 'm.csv'}")
    assert "已导出" in msg
    assert (tmp_path / "m.csv").exists()
    close_metrics_store()
