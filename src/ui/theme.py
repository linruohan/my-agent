"""UI Design Token 集中管理。"""

from __future__ import annotations

import customtkinter as ctk

# 圆角
INPUT_RADIUS = 6
BUBBLE_RADIUS = 12
CHIP_RADIUS = 12
AVATAR_RADIUS = 16

# 尺寸
AVATAR_SIZE = 32
BUBBLE_INSET = 3
BUBBLE_PAD_X = 26
BUBBLE_PAD_Y = 18
MESSAGE_GAP = 14
SIDE_INSET = 16

# 字体
FONT_FAMILY = "Segoe UI"
FONT_MONO = "Consolas"
FONT_BODY = 14
FONT_META = 12
FONT_CAPTION = 11

# 配色 (light, dark)
CHAT_BG = ("#f3f4f6", "#1a1a1e")
USER_BUBBLE = "#2563eb"
USER_BUBBLE_BORDER = "#3b82f6"
USER_FG = "#f8fafc"
ASSISTANT_BG = ("#ffffff", "#27272a")
ASSISTANT_BORDER = ("#e4e4e7", "#3f3f46")
ASSISTANT_FG = ("#18181b", "#e4e4e7")
AVATAR_USER_BG = ("#dbeafe", "#1e3a5f")
AVATAR_ASSISTANT_BG = ("#e4e4e7", "#3f3f46")
META_BG = ("#e5e7eb", "#27272a")
META_FG = ("#6b7280", "#a1a1aa")
META_ERROR = ("#dc2626", "#f87171")
META_SUCCESS = ("#16a34a", "#4ade80")
META_INFO = ("#2563eb", "#60a5fa")
CAPTION_FG = ("#9ca3af", "#71717a")
CODE_BG = ("#eef0f4", "#18181b")
TABLE_BG = ("#ececf1", "#34343f")
QUOTE_FG = ("#6b7280", "#a1a1aa")
LINK_FG = ("#2563eb", "#60a5fa")
LINK_FG_ON_USER = "#bfdbfe"
HR_FG = ("#d4d4d8", "#52525b")

USER_MAX_WIDTH_RATIO = 0.72
ASSISTANT_MAX_WIDTH_RATIO = 0.88

# 兼容旧名
CORNER_RADIUS = INPUT_RADIUS


def is_dark() -> bool:
    return ctk.get_appearance_mode().lower() == "dark"


def resolve(color: str | tuple[str, str]) -> str:
    if isinstance(color, tuple):
        return color[1] if is_dark() else color[0]
    return color
