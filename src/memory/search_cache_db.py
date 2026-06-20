"""兼容层：请使用 src.memory.search_cache.db。"""
from src.memory.search_cache.db import CacheRow, SearchCacheStore

__all__ = ["CacheRow", "SearchCacheStore"]
