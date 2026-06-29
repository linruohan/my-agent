"""兼容层：请使用 src.ui.prefs.font。"""

from src.ui.prefs import font_prefs
from src.ui.prefs.font import DEFAULT_FONT_ID, FONT_CATALOG

build_font_variables = font_prefs.build_variables
get_font_prefs = font_prefs.get_font_id
list_font_catalog = font_prefs.list_catalog
lxgw_font_installed = font_prefs.lxgw_font_installed
persist_font_prefs = font_prefs.persist

__all__ = [
    "DEFAULT_FONT_ID",
    "FONT_CATALOG",
    "build_font_variables",
    "get_font_prefs",
    "list_font_catalog",
    "lxgw_font_installed",
    "persist_font_prefs",
]
