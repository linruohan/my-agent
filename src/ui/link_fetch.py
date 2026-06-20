"""兼容层：请使用 src.ui.link.fetch。"""
from src.ui.link.fetch import *  # noqa: F403
from src.ui.link.fetch import (  # noqa: F401
    _extract_readable_text,
    _summarize_text,
    _validate_url,
    summarize_url,
)

__all__ = [
    "_extract_readable_text",
    "_summarize_text",
    "_validate_url",
    "summarize_url",
]
