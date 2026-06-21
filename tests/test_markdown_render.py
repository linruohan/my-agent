from __future__ import annotations

from src.ui.markdown_utils import compact_bubble_content, parse_table_block


def test_compact_bubble_content_removes_empty_lines():
    raw = "hello\n\n\nworld\n"
    assert compact_bubble_content(raw) == "hello\nworld"


def test_compact_bubble_content_preserves_code_block_blank_lines():
    raw = "text\n\n```\nline1\n\nline2\n```\n\nafter"
    assert compact_bubble_content(raw) == "text\n```\nline1\n\nline2\n```\nafter"


def test_parse_table_with_header():
    lines = [
        "| Name | Age |",
        "| --- | --- |",
        "| Alice | 30 |",
        "| Bob | 25 |",
    ]
    rows, has_header, nxt = parse_table_block(lines, 0)
    assert has_header is True
    assert nxt == 4
    assert rows == [["Name", "Age"], ["Alice", "30"], ["Bob", "25"]]


def test_parse_table_without_separator():
    lines = [
        "| A | B |",
        "| 1 | 2 |",
        "",
        "next",
    ]
    rows, has_header, nxt = parse_table_block(lines, 0)
    assert has_header is False
    assert nxt == 2
    assert rows == [["A", "B"], ["1", "2"]]


def test_parse_table_stops_at_blank():
    lines = ["| x |", "| y |", "", "text"]
    rows, _, nxt = parse_table_block(lines, 0)
    assert nxt == 2
    assert len(rows) == 2
