"""聊天布局等 UI 偏好。"""

from __future__ import annotations

from pathlib import Path

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


def get_work_dir() -> Path | None:
    settings = load_user_settings()
    ui = settings.get("ui", {}) or {}
    raw = (ui.get("work_dir") or "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser().resolve()
    return p if p.is_dir() else None


def persist_work_dir(path: str | Path) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        raise NotADirectoryError(f"不是有效目录: {p}")
    settings = load_user_settings()
    ui = settings.setdefault("ui", {})
    ui["work_dir"] = str(p)
    save_user_settings(settings)
    return p


def format_work_dir_display(path: Path | None) -> str:
    if path is None:
        return "点击选择工作目录"
    return str(path)
