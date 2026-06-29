"""聊天布局等 UI 偏好。"""

from __future__ import annotations

from src.infra.user_settings import load_user_settings, save_user_settings

DEFAULT_CHAT_WIDTH_PCT = 85
MIN_CHAT_WIDTH_PCT = 50
MAX_CHAT_WIDTH_PCT = 100


def _clamp_width_pct(value: int | float) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        n = DEFAULT_CHAT_WIDTH_PCT
    return max(MIN_CHAT_WIDTH_PCT, min(MAX_CHAT_WIDTH_PCT, n))


def get_chat_width_pct() -> int:
    settings = load_user_settings()
    ui = settings.get("ui", {}) or {}
    return _clamp_width_pct(ui.get("chat_width_pct", DEFAULT_CHAT_WIDTH_PCT))


def persist_chat_width_pct(pct: int | float) -> int:
    value = _clamp_width_pct(pct)
    settings = load_user_settings()
    ui = settings.setdefault("ui", {})
    ui["chat_width_pct"] = value
    save_user_settings(settings)
    return value
