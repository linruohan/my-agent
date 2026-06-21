"""Markdown 文本工具（与 UI 框架无关）。"""

from __future__ import annotations

import re

_TABLE_SEP = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


def compact_bubble_content(text: str) -> str:
    """去掉空行并收紧每行首尾空白；代码块内保留原样。"""
    if not text:
        return ""
    lines = text.splitlines()
    out: list[str] = []
    in_code = False
    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            out.append(line.rstrip())
            continue
        if in_code:
            out.append(line.rstrip())
            continue
        stripped = line.strip()
        if stripped:
            out.append(stripped)
    return "\n".join(out).strip()


def _is_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.count("|") >= 2


def _is_table_separator(line: str) -> bool:
    return bool(_TABLE_SEP.match(line.strip()))


def parse_table_block(lines: list[str], start: int) -> tuple[list[list[str]], bool, int]:
    """解析 GFM 表格块，返回 (rows, has_header, next_index)。"""
    rows: list[list[str]] = []
    i = start
    has_header = False

    while i < len(lines) and _is_table_row(lines[i]):
        if _is_table_separator(lines[i]):
            has_header = len(rows) > 0
            i += 1
            continue
        cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
        rows.append(cells)
        i += 1

    return rows, has_header, i
