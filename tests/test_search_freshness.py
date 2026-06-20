from __future__ import annotations

from src.tools.search import enrich_query, format_results, _detect_stale
from src.tools.search import SearchResult


def test_enrich_query_adds_year():
    q = enrich_query("Python 3.14 新特性")
    assert "2026" in q or str(__import__("datetime").datetime.now().year) in q


def test_enrich_query_keeps_existing_year():
    q = enrich_query("Python 3.14 2025 新特性")
    assert q.count("2025") >= 1


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
    text = format_results(results, "Python 3.14", "Python 3.14 2026 最新")
    assert "搜索时间" in text
    assert "实时网页摘要" in text
    assert "Python 3.14 发布说明" in text
