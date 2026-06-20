"""搜索缓存持久化与管理。"""

from src.memory.search_cache.admin import (
    cache_display_id,
    delete_cache_entry,
    format_cache_list,
    handle_cache_command,
)
from src.memory.search_cache.cache import (
    SearchCache,
    SearchCacheEntry,
    make_cache_key,
    text_similarity,
)
from src.memory.search_cache.db import CacheRow, SearchCacheStore

# 测试与内部使用
from src.memory.search_cache.cache import _normalize_query  # noqa: F401

__all__ = [
    "CacheRow",
    "SearchCache",
    "SearchCacheEntry",
    "SearchCacheStore",
    "cache_display_id",
    "delete_cache_entry",
    "format_cache_list",
    "handle_cache_command",
    "make_cache_key",
    "text_similarity",
]
