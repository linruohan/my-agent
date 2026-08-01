"""Playwright 资源拦截辅助。"""

from __future__ import annotations

from typing import Any

_BLOCKED_TYPES = frozenset({"image", "media", "font"})


def install_media_blocker(page: Any) -> None:
    """拦截图片/字体/媒体请求，加速导航与正文提取。"""

    def _handler(route: Any) -> None:
        try:
            if route.request.resource_type in _BLOCKED_TYPES:
                route.abort()
            else:
                route.continue_()
        except Exception:
            try:
                route.continue_()
            except Exception:
                pass

    page.route("**/*", _handler)
