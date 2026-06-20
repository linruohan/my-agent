"""兼容层：请使用 src.tools.web。"""
import httpx

from src.tools.web.core import SearchEngine, SearchResult, web_search_impl, _detect_stale
from src.tools.web import enrich_query, format_results, results_match_query, search_baidu, search_bing

__all__ = [
    "SearchEngine",
    "SearchResult",
    "_detect_stale",
    "enrich_query",
    "format_results",
    "httpx",
    "results_match_query",
    "search_baidu",
    "search_bing",
    "web_search_impl",
]
