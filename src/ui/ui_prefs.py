"""兼容层：请使用 src.ui.prefs.layout。"""

from src.ui.prefs import layout_prefs
from src.ui.prefs.layout import (
    DEFAULT_CHAT_WIDTH_PCT,
    MAX_CHAT_WIDTH_PCT,
    MIN_CHAT_WIDTH_PCT,
)

get_chat_width_pct = layout_prefs.get_chat_width_pct
persist_chat_width_pct = layout_prefs.persist_chat_width_pct
get_work_dir = layout_prefs.get_work_dir
persist_work_dir = layout_prefs.persist_work_dir
format_work_dir_display = layout_prefs.format_work_dir_display

__all__ = [
    "DEFAULT_CHAT_WIDTH_PCT",
    "MAX_CHAT_WIDTH_PCT",
    "MIN_CHAT_WIDTH_PCT",
    "format_work_dir_display",
    "get_chat_width_pct",
    "get_work_dir",
    "persist_chat_width_pct",
    "persist_work_dir",
]
