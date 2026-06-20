"""将 Markdown 渲染到 tk.Text 标签。"""

from __future__ import annotations

import io
import re
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import customtkinter as ctk
import httpx
from loguru import logger
from PIL import Image, ImageTk

from src.ui.theme import (
    CODE_BG,
    FONT_BODY,
    FONT_FAMILY,
    FONT_MONO,
    HR_FG,
    LINK_FG,
    LINK_FG_ON_USER,
    QUOTE_FG,
    TABLE_BG,
    resolve,
)

if TYPE_CHECKING:
    from tkinter import PhotoImage, Text

_IMAGE_LINE = re.compile(r"^!\[(.*?)\]\((.+?)\)\s*$")
_TABLE_SEP = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
_HR = re.compile(r"^(\*{3,}|-{3,}|_{3,})\s*$")
_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
_TASK = re.compile(r"^[-*+]\s+\[([ xX])\]\s+(.+)$")
_ORDERED = re.compile(r"^(\d+)\.\s+(.+)$")
_BULLET = re.compile(r"^[-*+]\s+(.+)$")
_BLOCKQUOTE = re.compile(r"^>\s?(.*)$")

_INLINE_RE = re.compile(
    r"(!\[.*?\]\(.+?\)|\[.*?\]\(.+?\)|~~.+?~~|\*\*.+?\*\*|__.+?__|\*.+?\*|_.+?_|`.+?`)"
)
_LINK_RE = re.compile(r"\[(.+?)\]\((.+?)\)")
_IMAGE_INLINE_RE = re.compile(r"!\[(.+?)\]\((.+?)\)")
_URL_INLINE_RE = re.compile(r"https?://[^\s\])<>\"']+")

_MAX_IMAGE_WIDTH = 380
_IMAGE_LINE_HEIGHT = 20


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


def _base_font(size: int | None = None) -> tuple[str, int]:
    return (FONT_FAMILY, size or FONT_BODY)


def _mono_font(size: int | None = None) -> tuple[str, int]:
    return (FONT_MONO, size or FONT_BODY - 2)


def _is_dark() -> bool:
    return ctk.get_appearance_mode().lower() == "dark"


def _configure_tags(tb: Text, *, on_user_bubble: bool = False) -> None:
    code_bg = resolve(CODE_BG)
    table_bg = resolve(TABLE_BG)
    quote_fg = resolve(QUOTE_FG)
    link_fg = LINK_FG_ON_USER if on_user_bubble else resolve(LINK_FG)
    hr_fg = resolve(HR_FG)

    tags = {
        "h1": {"font": (*_base_font(16), "bold"), "spacing1": 4, "spacing3": 2},
        "h2": {"font": (*_base_font(15), "bold"), "spacing1": 3, "spacing3": 1},
        "h3": {"font": (*_base_font(14), "bold"), "spacing1": 2, "spacing3": 1},
        "h4": {"font": (*_base_font(13), "bold"), "spacing1": 2, "spacing3": 0},
        "h5": {"font": (*_base_font(12), "bold"), "spacing1": 1, "spacing3": 0},
        "h6": {"font": (*_base_font(11), "bold"), "spacing1": 1, "spacing3": 0},
        "bold": {"font": (*_base_font(), "bold")},
        "italic": {"font": (*_base_font(), "italic")},
        "strike": {"overstrike": 1, "foreground": quote_fg},
        "code": {"font": _mono_font(), "background": code_bg},
        "codeblock": {
            "font": _mono_font(12),
            "background": code_bg,
            "lmargin1": 6,
            "lmargin2": 6,
            "spacing1": 1,
            "spacing3": 1,
        },
        "link": {"foreground": link_fg, "underline": True},
        "quote": {"foreground": quote_fg, "lmargin1": 10, "lmargin2": 10},
        "bullet": {"lmargin1": 10, "lmargin2": 22, "spacing1": 0, "spacing3": 1},
        "table": {"font": _mono_font(11), "background": table_bg, "lmargin1": 2, "lmargin2": 2},
        "table_header": {
            "font": (*_mono_font(11), "bold"),
            "background": table_bg,
            "lmargin1": 2,
            "lmargin2": 2,
        },
        "table_sep": {"font": _mono_font(11), "foreground": hr_fg, "lmargin1": 2, "lmargin2": 2},
        "hr": {"foreground": hr_fg},
        "image_alt": {"foreground": quote_fg, "font": (*_base_font(11), "italic")},
    }
    for name, opts in tags.items():
        tb.tag_configure(name, **opts)


@dataclass
class MarkdownContext:
    tb: Text
    images: list[Any] = field(default_factory=list)
    extra_lines: int = 0
    host: Any | None = None
    link_id: int = 0


def _open_url(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception as exc:
        logger.warning("打开链接失败 {}: {}", url, exc)


def _insert_link(ctx: MarkdownContext, label: str, url: str) -> None:
    """插入可点击链接（独立 tag + Button-1 绑定）。"""
    tb = ctx.tb
    url = url.strip()
    if not url:
        tb.insert("end", label, "link")
        return

    tag = f"md_link_{ctx.link_id}"
    ctx.link_id += 1
    tb.insert("end", label, ("link", tag))
    if ctx.host is not None:
        urls = getattr(ctx.host, "_md_link_urls", None)
        if urls is not None:
            urls[tag] = url
    else:
        tb.tag_bind(tag, "<Button-1>", lambda _e, u=url: _open_url(u))
    tb.tag_bind(tag, "<Enter>", lambda _e: tb.configure(cursor="hand2"))
    tb.tag_bind(tag, "<Leave>", lambda _e: tb.configure(cursor="arrow"))


def _insert_plain_with_urls(ctx: MarkdownContext, text: str) -> None:
    tb = ctx.tb
    pos = 0
    for m in _URL_INLINE_RE.finditer(text):
        if m.start() > pos:
            tb.insert("end", text[pos : m.start()])
        url = m.group(0).rstrip(".,;:!?)")
        _insert_link(ctx, url, url)
        pos = m.end()
    if pos < len(text):
        tb.insert("end", text[pos:])


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


def _format_table_row(cells: list[str], widths: list[int]) -> str:
    parts: list[str] = []
    for idx, width in enumerate(widths):
        cell = cells[idx] if idx < len(cells) else ""
        parts.append(cell.ljust(width))
    return " | ".join(parts)


def _render_table(ctx: MarkdownContext, rows: list[list[str]], has_header: bool) -> None:
    if not rows:
        return
    col_count = max(len(r) for r in rows)
    widths = [3] * col_count
    for row in rows:
        for j, cell in enumerate(row):
            if j < col_count:
                widths[j] = max(widths[j], len(cell))

    tb = ctx.tb
    start = 0
    if has_header and rows:
        tb.insert("end", _format_table_row(rows[0], widths) + "\n", "table_header")
        tb.insert("end", "-+-".join("-" * w for w in widths) + "\n", "table_sep")
        start = 1

    for row in rows[start:]:
        tb.insert("end", _format_table_row(row, widths) + "\n", "table")


def _load_image(url_or_path: str, *, max_width: int = _MAX_IMAGE_WIDTH) -> tuple[PhotoImage | None, int, int]:
    try:
        if url_or_path.startswith(("http://", "https://")):
            resp = httpx.get(url_or_path, timeout=12, follow_redirects=True)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content))
        else:
            path = Path(url_or_path.strip()).expanduser()
            if not path.is_file():
                return None, 0, 0
            img = Image.open(path)

        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")

        w, h = img.size
        if w > max_width:
            ratio = max_width / w
            img = img.resize((max_width, max(1, int(h * ratio))), Image.Resampling.LANCZOS)

        photo = ImageTk.PhotoImage(img)
        return photo, img.width, img.height
    except Exception as exc:
        logger.debug("图片加载失败 {}: {}", url_or_path, exc)
        return None, 0, 0


def _render_image(ctx: MarkdownContext, alt: str, src: str) -> None:
    tb = ctx.tb
    photo, _w, h = _load_image(src)
    if photo is None:
        tb.insert("end", f"[图片: {alt or 'image'}] ", "image_alt")
        _insert_link(ctx, src, src)
        tb.insert("end", "\n")
        return

    ctx.images.append(photo)
    ctx.extra_lines += max(1, h // _IMAGE_LINE_HEIGHT)
    if alt:
        tb.insert("end", alt + "\n", "image_alt")
    tb.image_create("end", image=photo, padx=4, pady=4)
    tb.insert("end", "\n")


def _insert_inline(ctx: MarkdownContext, text: str) -> None:
    tb = ctx.tb
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            _insert_plain_with_urls(ctx, text[pos : m.start()])
        chunk = m.group(0)

        img = _IMAGE_INLINE_RE.match(chunk)
        if img:
            _render_image(ctx, img.group(1), img.group(2))
        elif chunk.startswith("~~") and chunk.endswith("~~"):
            tb.insert("end", chunk[2:-2], "strike")
        elif chunk.startswith("**") and chunk.endswith("**"):
            tb.insert("end", chunk[2:-2], "bold")
        elif chunk.startswith("__") and chunk.endswith("__"):
            tb.insert("end", chunk[2:-2], "bold")
        elif chunk.startswith("*") and chunk.endswith("*"):
            tb.insert("end", chunk[1:-1], "italic")
        elif chunk.startswith("_") and chunk.endswith("_"):
            tb.insert("end", chunk[1:-1], "italic")
        elif chunk.startswith("`") and chunk.endswith("`"):
            tb.insert("end", chunk[1:-1], "code")
        else:
            link = _LINK_RE.match(chunk)
            if link:
                _insert_link(ctx, link.group(1), link.group(2))
            else:
                tb.insert("end", chunk)
        pos = m.end()
    if pos < len(text):
        _insert_plain_with_urls(ctx, text[pos:])


def _render_paragraph(ctx: MarkdownContext, text: str) -> None:
    _insert_inline(ctx, text)
    ctx.tb.insert("end", "\n")


def _get_text_widget(target: Any):
    if hasattr(target, "text_widget"):
        return target.text_widget
    if hasattr(target, "_textbox"):
        return target._textbox
    return target


def set_plain_text_content(target: Any, content: str, *, text_color: str | None = None) -> None:
    """写入纯文本，并自动识别可点击 URL。"""
    tb = _get_text_widget(target)
    if hasattr(target, "set_editable"):
        target.set_editable()
    else:
        tb.configure(state="normal")
    tb.delete("1.0", "end")
    on_user = getattr(target, "_chat_role", None) == "user"
    _configure_tags(tb, on_user_bubble=on_user)
    if text_color:
        tb.configure(fg=text_color)
    ctx = MarkdownContext(tb=tb, host=target if hasattr(target, "_md_images") else None)
    host = ctx.host
    if host is not None:
        host._md_link_urls = {}
    content = compact_bubble_content(content)
    _insert_plain_with_urls(ctx, content)
    if hasattr(target, "set_readonly"):
        target.set_readonly()
    else:
        tb.configure(state="disabled")


def render_markdown(target: Any, content: str, *, text_color: str | None = None) -> None:
    """清空并将 markdown 写入 BubbleText / tk.Text / CTkTextbox。"""
    tb = _get_text_widget(target)
    host = target if hasattr(target, "_md_images") else None

    if hasattr(target, "set_editable"):
        target.set_editable()
    else:
        tb.configure(state="normal")

    tb.delete("1.0", "end")
    on_user = getattr(target, "_chat_role", None) == "user"
    _configure_tags(tb, on_user_bubble=on_user)
    if text_color:
        tb.configure(fg=text_color)

    ctx = MarkdownContext(tb=tb, host=host)
    if host is not None:
        host._md_images = ctx.images
        host._md_extra_lines = 0
        host._md_link_urls = {}

    content = compact_bubble_content(content)
    lines = content.splitlines()
    i = 0
    in_code = False
    code_buf: list[str] = []

    while i < len(lines):
        line = lines[i]

        if line.strip().startswith("```"):
            if in_code:
                tb.insert("end", "\n".join(code_buf) + "\n", "codeblock")
                code_buf.clear()
                in_code = False
            else:
                in_code = True
            i += 1
            continue

        if in_code:
            code_buf.append(line)
            i += 1
            continue

        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if _is_table_row(line) and (
            i + 1 < len(lines) and (_is_table_separator(lines[i + 1]) or _is_table_row(lines[i + 1]))
        ):
            rows, has_header, i = parse_table_block(lines, i)
            _render_table(ctx, rows, has_header)
            continue

        img_match = _IMAGE_LINE.match(stripped)
        if img_match:
            _render_image(ctx, img_match.group(1), img_match.group(2))
            i += 1
            continue

        if _HR.match(stripped):
            tb.insert("end", "─" * 40 + "\n", "hr")
            i += 1
            continue

        heading = _HEADING.match(stripped)
        if heading:
            level = min(len(heading.group(1)), 6)
            tb.insert("end", heading.group(2) + "\n", f"h{level}")
            i += 1
            continue

        task = _TASK.match(stripped)
        if task:
            mark = "☑" if task.group(1).lower() == "x" else "☐"
            tb.insert("end", f"{mark} ", "bullet")
            _insert_inline(ctx, task.group(2) + "\n")
            i += 1
            continue

        bullet = _BULLET.match(stripped)
        if bullet:
            tb.insert("end", "• ", "bullet")
            _insert_inline(ctx, bullet.group(1) + "\n")
            i += 1
            continue

        ordered = _ORDERED.match(stripped)
        if ordered:
            tb.insert("end", f"{ordered.group(1)}. ")
            _insert_inline(ctx, ordered.group(2) + "\n")
            i += 1
            continue

        quote = _BLOCKQUOTE.match(line)
        if quote:
            start = tb.index("end-1c")
            _insert_inline(ctx, quote.group(1) + "\n")
            tb.tag_add("quote", start, "end-1c")
            i += 1
            continue

        _render_paragraph(ctx, line)
        i += 1

    if in_code and code_buf:
        tb.insert("end", "\n".join(code_buf) + "\n", "codeblock")

    # 去掉末尾多余换行，避免占位空行
    end_index = tb.index("end-1c")
    if end_index != "1.0" and tb.get("end-2c", "end-1c") == "\n":
        tb.delete("end-2c", "end-1c")

    if host is not None:
        host._md_extra_lines = ctx.extra_lines

    if hasattr(target, "set_readonly"):
        target.set_readonly()
    else:
        tb.configure(state="disabled")


def _count_display_lines(tb: Text) -> int:
    tb.update_idletasks()
    try:
        result = tb.count("1.0", "end-1c", "displaylines")
        if result and int(result[0]) > 0:
            return int(result[0])
    except Exception:
        pass

    logical = max(1, int(float(tb.index("end-1c"))))
    content = tb.get("1.0", "end-1c")
    width = tb.winfo_width() or 380
    chars_per_line = max(24, width // 9)
    wrapped = sum(max(1, (len(line) + chars_per_line - 1) // chars_per_line) for line in content.splitlines())
    return max(logical, wrapped)


def fit_text_height(
    target: Any,
    *,
    max_lines: int = 200,
    min_lines: int = 1,
) -> None:
    tb = _get_text_widget(target)
    tb.update_idletasks()
    if hasattr(target, "update_idletasks"):
        target.update_idletasks()

    content = tb.get("1.0", "end-1c")
    if not content.strip():
        tb.configure(height=min_lines)
        return

    display_lines = _count_display_lines(tb)
    extra = getattr(target, "_md_extra_lines", 0)
    height = max(min_lines, min(display_lines + extra, max_lines))
    tb.configure(height=height)


def fit_bubble_size(target: Any, *, max_width: int | None = None, **height_kwargs: int) -> None:
    if max_width is not None and hasattr(target, "set_max_width"):
        target.set_max_width(max_width)
    elif hasattr(target, "fit_width"):
        target.fit_width()
    fit_text_height(target, **height_kwargs)


def schedule_fit_text_height(
    target: Any,
    *,
    on_done: Any | None = None,
    max_width: int | None = None,
    **kwargs: int,
) -> None:
    """布局稳定后重算宽高（合并多次 refit，避免抖动）。"""
    scheduler = target if hasattr(target, "after") else _get_text_widget(target)
    pending = getattr(target, "_fit_after_ids", None)
    if pending is None:
        pending = []
        target._fit_after_ids = pending
    for job in pending:
        try:
            scheduler.after_cancel(job)
        except Exception:
            pass
    pending.clear()

    fit_bubble_size(target, max_width=max_width, **kwargs)

    def _final() -> None:
        fit_bubble_size(target, max_width=max_width, **kwargs)
        pending.clear()
        if on_done:
            on_done()

    pending.append(scheduler.after_idle(_final))


# 兼容旧名
fit_textbox_height = fit_text_height
schedule_fit_textbox_height = schedule_fit_text_height
