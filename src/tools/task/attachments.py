"""从任务描述中提取本地文件路径与链接附件。"""

from __future__ import annotations

import re
from typing import Any

from src.ui.open_local import clean_local_path

_RE_URL = re.compile(r"https?://[^\s,，;；、<>\"'|\]]+", re.IGNORECASE)
_RE_WIN_PATH = re.compile(
    r"[A-Za-z]:[\\/](?:[^\s<>\"'`|,，;；、]+[\\/])*[^\s<>\"'`|,，;；、]+"
)


def _dedupe_attachments(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for item in items:
        val = (item.get("value") or "").strip()
        if not val or val in seen:
            continue
        seen.add(val)
        out.append({"type": item["type"], "value": val})
    return out


def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(not (end <= s or start >= e) for s, e in spans)


def extract_attachments(text: str) -> tuple[str, list[dict[str, str]]]:
    """从文本提取 URL 与 Windows 绝对路径，返回清理后的文本与附件列表。"""
    raw = (text or "").strip()
    if not raw:
        return "", []

    found: list[dict[str, str]] = []
    remove_spans: list[tuple[int, int]] = []

    for m in _RE_URL.finditer(raw):
        url = m.group(0).rstrip(".,;:!?)")
        if not url:
            continue
        found.append({"type": "url", "value": url})
        remove_spans.append((m.start(), m.end()))

    for m in _RE_WIN_PATH.finditer(raw):
        if _overlaps(m.start(), m.end(), remove_spans):
            continue
        path = clean_local_path(m.group(0))
        if len(path) < 4:
            continue
        found.append({"type": "file", "value": path})
        remove_spans.append((m.start(), m.end()))

    if not remove_spans:
        return raw, _dedupe_attachments(found)

    remove_spans.sort(key=lambda x: x[0])
    merged: list[tuple[int, int]] = []
    for s, e in remove_spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    parts: list[str] = []
    cursor = 0
    for s, e in merged:
        if s > cursor:
            parts.append(raw[cursor:s])
        cursor = e
    if cursor < len(raw):
        parts.append(raw[cursor:])

    cleaned = re.sub(r"[\s,，;；、]+", " ", "".join(parts)).strip()
    return cleaned, _dedupe_attachments(found)


def apply_content_attachments(title: str, content: str) -> tuple[str, str, list[dict[str, str]]]:
    """分别扫描标题与内容，剥离附件并去重合并。"""
    t_clean, att_title = extract_attachments(title or "")
    c_clean, att_content = extract_attachments(content or "")
    attachments = _dedupe_attachments(att_title + att_content)
    return t_clean, c_clean, attachments


def merge_attachments(
    existing: list[dict[str, str]] | None,
    new_items: list[dict[str, str]],
) -> list[dict[str, str]]:
    return _dedupe_attachments(list(existing or []) + list(new_items or []))
