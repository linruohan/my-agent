from __future__ import annotations

from src.ui.message_utils import normalize_user_message


def test_normalize_user_message_strips_edges():
    assert normalize_user_message("  \n\n  hello  \n  ") == "hello"


def test_normalize_user_message_removes_blank_lines_at_edges():
    assert normalize_user_message("\n\nline1\n\nline2\n\n\n") == "line1\nline2"


def test_normalize_user_message_trims_each_line():
    assert normalize_user_message("  a  \n  b  ") == "a\nb"
