"""枚举操作系统已安装字体。"""

from __future__ import annotations

import sys

_font_cache: list[str] | None = None

SYSTEM_DEFAULT_LABEL = "系统默认"
DEFAULT_FONT_ID = "system"

SYSTEM_FONT_STACK = (
    '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, sans-serif'
)
MONO_FONT_STACK = '"Cascadia Code", Consolas, monospace'

# 旧版内置字体 id，迁移时回退为系统默认
_LEGACY_FONT_IDS = frozenset({"lxgw-wenkai-gb"})


def invalidate_font_cache() -> None:
    global _font_cache
    _font_cache = None


def list_system_fonts(*, refresh: bool = False) -> list[str]:
    """返回已安装字体族名（去重、排序）。"""
    global _font_cache
    if _font_cache is None or refresh:
        if sys.platform == "win32":
            _font_cache = _enumerate_windows_fonts()
        else:
            _font_cache = _enumerate_fallback_fonts()
    return list(_font_cache)


def _enumerate_windows_fonts() -> list[str]:
    import win32gui

    fonts: set[str] = set()

    def callback(logfont, _textmetric, _fonttype, _names) -> bool:
        name = (logfont.lfFaceName or "").strip()
        if name and not name.startswith("@"):
            fonts.add(name)
        return True

    hdc = win32gui.GetDC(0)
    try:
        win32gui.EnumFontFamilies(hdc, None, callback, None)
    finally:
        win32gui.ReleaseDC(0, hdc)
    return sorted(fonts, key=str.casefold)


def _enumerate_fallback_fonts() -> list[str]:
    """非 Windows 平台的常见字体回退列表。"""
    return sorted(
        {
            "Arial",
            "Helvetica Neue",
            "PingFang SC",
            "Hiragino Sans GB",
            "Microsoft YaHei",
            "Noto Sans CJK SC",
            "Segoe UI",
            "SF Pro Text",
            "Source Han Sans SC",
        },
        key=str.casefold,
    )


def css_font_family(font_id: str) -> tuple[str, str]:
    """生成 UI 字体与等宽字体的 CSS font-family 值。"""
    if font_id == DEFAULT_FONT_ID or not font_id:
        return SYSTEM_FONT_STACK, MONO_FONT_STACK
    quoted = f'"{font_id}"'
    return (
        f'{quoted}, "Segoe UI", system-ui, sans-serif',
        f'{quoted}, {MONO_FONT_STACK}',
    )


def normalize_font_id(font_id: str | None) -> str:
    raw = (font_id or DEFAULT_FONT_ID).strip()
    if not raw or raw in _LEGACY_FONT_IDS:
        return DEFAULT_FONT_ID
    return raw
