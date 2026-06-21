from __future__ import annotations

from src.ui.markdown_utils import compact_bubble_content


def normalize_user_message(text: str) -> str:
    return compact_bubble_content(text)
