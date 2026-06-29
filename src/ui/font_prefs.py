"""兼容层：请使用 src.ui.prefs.font。"""

from src.ui.prefs import font_prefs
from src.ui.prefs.font import DEFAULT_FONT_ID
from src.ui.prefs.system_fonts import list_system_fonts

build_font_variables = font_prefs.build_variables
get_font_prefs = font_prefs.get_font_id
list_font_catalog = font_prefs.list_catalog
persist_font_prefs = font_prefs.persist

__all__ = [
    "DEFAULT_FONT_ID",
    "build_font_variables",
    "get_font_prefs",
    "list_font_catalog",
    "list_system_fonts",
    "persist_font_prefs",
]
