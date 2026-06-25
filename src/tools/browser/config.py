"""浏览器自动化配置。"""

from __future__ import annotations

from typing import Any

from src.infra.config import load_app_config
from src.infra.config import load_search_config


def load_browser_config() -> dict[str, Any]:
    app = load_app_config()
    cfg = app.get("browser", {}) or {}
    search = load_search_config().get("search", {})
    ua = cfg.get("user_agent") or search.get(
        "user_agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    )
    return {
        "headless": bool(cfg.get("headless", True)),
        "timeout_ms": int(cfg.get("timeout_ms", 30000) or 30000),
        "navigation_timeout_ms": int(cfg.get("navigation_timeout_ms", 45000) or 45000),
        "max_text_chars": int(cfg.get("max_text_chars", 8000) or 8000),
        "screenshot_dir": str(cfg.get("screenshot_dir", "data/workspace/browser_screenshots")),
        "user_agent": str(ua),
        "idle_close_sec": int(cfg.get("idle_close_sec", 600) or 600),
        "max_sessions": int(cfg.get("max_sessions", 8) or 8),
        "idle_cleanup_interval_sec": int(cfg.get("idle_cleanup_interval_sec", 120) or 120),
    }
