from __future__ import annotations

from src.ui.clipboard import copy_to_clipboard


def test_copy_to_clipboard_empty():
    assert copy_to_clipboard("") is False


def test_copy_to_clipboard_text():
    assert copy_to_clipboard("hello copy test") is True
