"""中国天气网 weather 图标雪碧图（blue80.png）切分逻辑。"""

from __future__ import annotations

import html
import re

SPRITE_80_URL = "https://i.tq121.com.cn/i/weather2015/png/blue80.png"

# blue80.png 实际尺寸（非 CSS 推算值）
_SHEET_W = 960
_SHEET_H = 640
_CELL = 80
_NIGHT_ROW_OFFSET = 320  # 夜间图标从 y=-320px 起

# d32+ 等非标准网格坐标（与 headStyle_1.css 一致）
_EXTRA_POSITIONS: dict[str, str] = {
    "d32": "-720px -80px",
    "d33": "-480px -240px",
    "d49": "-720px -160px",
    "d53": "-560px -240px",
    "d54": "-800px 0",
    "d55": "-800px -80px",
    "d56": "-800px -160px",
    "d57": "-720px 0",
    "d58": "-720px -240px",
    "n32": "-720px -400px",
    "n33": "-480px -560px",
    "n49": "-720px -480px",
    "n53": "-560px -560px",
    "n54": "-800px -320px",
    "n55": "-800px -400px",
    "n56": "-800px -480px",
    "n57": "-720px -320px",
    "n58": "-720px -560px",
}

_CODE_RE = re.compile(r"^([dn])(\d{2})$")


def _normalize_code(code: str) -> str:
    return (code or "").strip().lower()


def _px(value: float) -> str:
    return "0" if value == 0 else f"{value:g}px"


def icon_position(code: str, *, size: int = 80) -> str:
    """返回 CSS background-position（80px 原始坐标，不做缩放）。"""
    code = _normalize_code(code)
    if not _CODE_RE.match(code):
        return ""

    if code in _EXTRA_POSITIONS:
        return _EXTRA_POSITIONS[code]

    num = int(code[2:])
    row, col = divmod(num, 9)
    x = -col * _CELL
    if code[0] == "d":
        y = -row * _CELL
    else:
        y = -(_NIGHT_ROW_OFFSET + row * _CELL)
    return f"{_px(x)} {_px(y)}"


def icon_sprite_url(code: str = "") -> str:
    """返回天气图标雪碧图 URL（blue80.png）。"""
    return SPRITE_80_URL


def icon_sprite_html(
    code: str,
    *,
    size: int = 48,
    alt: str = "",
    css_class: str = "wx-icon",
) -> str:
    """生成内联雪碧图 span（80px 原坐标 + transform 缩放，与原站一致）。"""
    code = _normalize_code(code)
    if not code or not _CODE_RE.match(code):
        return ""

    pos = icon_position(code)
    if not pos:
        return ""

    scale = size / _CELL
    title = f' title="{html.escape(alt)}"' if alt else ""
    inner_style = (
        f"width:{_CELL}px;height:{_CELL}px;"
        f"background-image:url({SPRITE_80_URL});"
        f"background-repeat:no-repeat;"
        f"background-position:{pos};"
        f"transform:scale({scale:g});transform-origin:0 0;"
    )
    wrap_style = f"width:{size}px;height:{size}px;overflow:hidden;display:inline-block;flex-shrink:0;"
    return (
        f'<span class="{css_class} wx-icon-sprite-wrap" data-code="{html.escape(code)}"'
        f'{title} style="{wrap_style}" role="img" aria-label="{html.escape(alt)}">'
        f'<span class="wx-icon-sprite" style="{inner_style}"></span></span>'
    )
