"""会话历史加载上限。"""

from __future__ import annotations

from src.infra.config import load_app_config


def session_history_limit() -> int | None:
    """返回最近 N 条事件上限；None/0 表示不限制。"""
    cfg = load_app_config().get("app", {}) or {}
    raw = cfg.get("session_history_limit", 200)
    try:
        n = int(raw or 0)
    except (TypeError, ValueError):
        n = 200
    return n if n > 0 else None


def session_history_page_size() -> int:
    """向上翻页每次加载条数。"""
    cfg = load_app_config().get("app", {}) or {}
    raw = cfg.get("session_history_page_size", 50)
    try:
        n = int(raw or 50)
    except (TypeError, ValueError):
        n = 50
    return max(1, min(n, 500))
