"""搜索缓存管理命令（/cache）。"""

from __future__ import annotations

import hashlib
import html
import re

from src.memory.search_cache.cache import SearchCache
from src.memory.search_cache.db import CacheRow

_HIGHLIGHT_RE = re.compile(r"([^<>&]+)")


def cache_display_id(cache_key: str) -> str:
    return hashlib.md5(cache_key.encode("utf-8")).hexdigest()[:8]


def _title_of(row: CacheRow) -> str:
    if row.search_query.strip():
        return row.search_query.strip()[:80]
    if row.user_queries:
        return row.user_queries[0][:80]
    return row.cache_key[:80]


def _find_by_id(store_rows: list[CacheRow], token: str) -> CacheRow | None:
    token = (token or "").strip().lower()
    if not token:
        return None
    for row in store_rows:
        if row.cache_key.lower() == token or row.cache_key.lower().startswith(token):
            return row
        if cache_display_id(row.cache_key) == token:
            return row
    return None


def _highlight(text: str, keyword: str) -> str:
    if not keyword:
        return html.escape(text)
    parts = re.split(re.escape(keyword), text, flags=re.IGNORECASE)
    if len(parts) == 1:
        return html.escape(text)
    out: list[str] = []
    idx = 0
    lower = text.lower()
    kw = keyword.lower()
    pos = 0
    for part in parts:
        out.append(html.escape(part))
        pos += len(part)
        if idx < len(parts) - 1:
            start = lower.find(kw, pos - len(part))
            if start >= 0:
                orig = text[start : start + len(keyword)]
                out.append(f'<mark class="kw-hl">{html.escape(orig)}</mark>')
                pos = start + len(keyword)
        idx += 1
    return "".join(out)


def format_cache_list(cache: SearchCache, *, keyword: str = "") -> str:
    rows = cache._store.list_active()
    if keyword:
        kw = keyword.lower()
        rows = [
            r
            for r in rows
            if kw in r.search_query.lower()
            or kw in r.cache_key.lower()
            or any(kw in uq.lower() for uq in r.user_queries)
        ]

    if not rows:
        return "暂无缓存条目。" if not keyword else f"未找到与「{keyword}」相关的缓存。"

    lines = ["| ID | 标题 |", "| --- | --- |"]
    for row in rows:
        cid = cache_display_id(row.cache_key)
        title = _title_of(row).replace("|", "\\|")
        lines.append(f"| `{cid}` | {title} |")
    header = "搜索缓存列表：" if not keyword else f"搜索缓存（关键字「{keyword}」）："
    return header + "\n\n" + "\n".join(lines)


def delete_cache_entry(cache: SearchCache, cache_id: str) -> str:
    rows = cache._store.list_active()
    row = _find_by_id(rows, cache_id)
    if not row:
        return f"未找到缓存 ID：{cache_id}"
    cache._store.delete_by_key(row.cache_key)
    return f"已删除缓存 `{cache_display_id(row.cache_key)}`：{_title_of(row)}"


def handle_cache_command(args: str, cache: SearchCache) -> str:
    body = (args or "").strip()
    if not body or body.lower() == "list":
        return format_cache_list(cache)
    parts = body.split(None, 1)
    sub = parts[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""
    if sub == "list":
        return format_cache_list(cache)
    if sub == "rm" and rest:
        return delete_cache_entry(cache, rest)
    if sub == "rm":
        return "用法：/cache rm <缓存ID>"
    return format_cache_list(cache, keyword=body)
