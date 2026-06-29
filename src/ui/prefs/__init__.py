"""UI 偏好模块：布局、字体、主题。"""

from src.ui.prefs.font import FONT_CATALOG, DEFAULT_FONT_ID, FontPrefs
from src.ui.prefs.layout import (
    DEFAULT_CHAT_WIDTH_PCT,
    MAX_CHAT_WIDTH_PCT,
    MIN_CHAT_WIDTH_PCT,
    LayoutPrefs,
)
from src.ui.prefs.theme import ThemePrefs

layout_prefs = LayoutPrefs()
font_prefs = FontPrefs()
theme_prefs = ThemePrefs()

__all__ = [
    "DEFAULT_CHAT_WIDTH_PCT",
    "DEFAULT_FONT_ID",
    "FONT_CATALOG",
    "FontPrefs",
    "LayoutPrefs",
    "MAX_CHAT_WIDTH_PCT",
    "MIN_CHAT_WIDTH_PCT",
    "ThemePrefs",
    "font_prefs",
    "layout_prefs",
    "theme_prefs",
]
