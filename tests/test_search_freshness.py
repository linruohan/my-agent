from __future__ import annotations

from src.tools.search import (
    enrich_query,
    format_results,
    results_match_query,
    _detect_stale,
)
from src.tools.search import SearchResult


def test_enrich_query_preserves_version_query():
    q = enrich_query("Python 3.14 新特性")
    assert q == "Python 3.14 新特性"
    assert "2026" not in q


def test_enrich_query_adds_year_for_generic():
    q = enrich_query("今日科技新闻")
    year = str(__import__("datetime").datetime.now().year)
    assert year in q


def test_enrich_query_keeps_existing_year():
    q = enrich_query("Python 3.14 2025 新特性")
    assert q == "Python 3.14 2025 新特性"


def test_results_match_query_detects_irrelevant_bing():
    bad = [
        SearchResult("Welcome to Python.org", "https://python.org", "general", "bing"),
        SearchResult("Download Python", "https://python.org/downloads", "general", "bing"),
    ]
    assert not results_match_query(bad, "Python 3.14 新特性")


def test_results_match_query_accepts_relevant():
    good = [
        SearchResult(
            "Python 3.14 有什么新变化 — Python 3.14.6 文档",
            "https://docs.python.org",
            "Python 3.14 新特性",
            "baidu",
        ),
    ]
    assert results_match_query(good, "Python 3.14 新特性")


def test_detect_stale_old_year():
    hint = _detect_stale("截至目前（2024年），Python 3.14 尚未发布")
    assert "过时" in hint or "2024" in hint


def test_format_results_includes_timestamp():
    results = [
        SearchResult(
            title="Python 3.14 发布说明",
            url="https://example.com",
            snippet="Python 3.14 于 2025 年 10 月发布",
            engine="baidu",
        )
    ]
    text = format_results(results, "Python 3.14", "Python 3.14")
    assert "搜索时间" in text
    assert "实时网页摘要" in text
    assert "Python 3.14 发布说明" in text
