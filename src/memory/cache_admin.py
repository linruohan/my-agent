"""兼容层：请使用 src.memory.search_cache.admin。"""
from src.memory.search_cache.admin import *  # noqa: F403
from src.memory.search_cache.admin import (
    cache_display_id,
    delete_cache_entry,
    format_cache_list,
    handle_cache_command,
)

__all__ = [
    "cache_display_id",
    "delete_cache_entry",
    "format_cache_list",
    "handle_cache_command",
]
