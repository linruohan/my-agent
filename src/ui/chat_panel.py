from __future__ import annotations

import re

import customtkinter as ctk

from src.ui.bubble_text import BubbleText, resolve_theme_color
from src.ui.markdown_render import (
    fit_bubble_size,
    render_markdown,
    schedule_fit_text_height,
    set_plain_text_content,
)
from src.ui.theme import CORNER_RADIUS


def normalize_user_message(text: str) -> str:
    """去掉首尾空白与空行，并去除每行首尾空格。"""
    from src.ui.markdown_render import compact_bubble_content

    return compact_bubble_content(text)


class ChatPanel(ctk.CTkFrame):
    """聊天消息展示区：Markdown 渲染，用户右对齐，助理左对齐。"""

    # 用户气泡：饱和蓝 + 浅蓝描边
    _USER_BG = "#2563eb"
    _USER_BORDER = "#3b82f6"
    _USER_FG = "#f8fafc"
    # 助理气泡：与窗口背景拉开层次
    _ASSISTANT_BG = ("#f4f4f5", "#3f3f46")
    _ASSISTANT_BORDER = ("#e4e4e7", "#52525b")
    _ASSISTANT_FG = ("#18181b", "#e4e4e7")
    _ROLE_LABEL_FG = ("gray40", "gray60")
    _TOOL_FG = ("#6b7280", "#71717a")
    _H_PAD = 24
    _USER_MAX_WIDTH_RATIO = 0.76
    _ASSISTANT_MAX_WIDTH_RATIO = 0.94
    _STREAM_DEBOUNCE_MS = 80
    _SCROLL_DEBOUNCE_MS = 60

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._scroll.bind("<Configure>", self._on_scroll_configure)

        self._streaming = False
        self._stream_buffer = ""
        self._assistant_bubble: BubbleText | None = None
        self._max_width = 640

        self._stream_update_job: str | None = None
        self._scroll_job: str | None = None
        self._tool_status_row: ctk.CTkFrame | None = None
        self._tool_status_label: ctk.CTkLabel | None = None

    def append_user(self, content: str) -> None:
        content = normalize_user_message(content)
        if not content:
            return
        self._clear_tool_status()
        self._add_bubble(
            role="user",
            title="我",
            content=content,
            use_markdown=True,
        )

    def begin_assistant(self) -> None:
        self._streaming = True
        self._stream_buffer = ""
        self._clear_tool_status()
        self._assistant_bubble = self._add_bubble_row(role="assistant", title="助理")

    def append_token(self, token: str) -> None:
        self._stream_buffer += token
        if self._stream_update_job is not None:
            self.after_cancel(self._stream_update_job)
        self._stream_update_job = self.after(self._STREAM_DEBOUNCE_MS, self._apply_stream_update)

    def end_assistant(self) -> None:
        if self._stream_update_job is not None:
            self.after_cancel(self._stream_update_job)
            self._stream_update_job = None

        bubble = self._assistant_bubble
        if bubble:
            self._clear_tool_status()
            if self._stream_buffer:
                render_markdown(bubble, self._stream_buffer, text_color=self._role_text_color("assistant"))
            schedule_fit_text_height(
                bubble,
                max_width=self._bubble_max_width("assistant"),
                on_done=self._scroll_to_bottom,
            )
        self._streaming = False
        self._stream_buffer = ""
        self._assistant_bubble = None

    def reset_assistant_for_tool(self) -> None:
        """工具调用前移除规划语气泡，后续 token 将开启新的汇总回复。"""
        if self._stream_update_job is not None:
            self.after_cancel(self._stream_update_job)
            self._stream_update_job = None
        if self._assistant_bubble is not None:
            self._destroy_bubble_row(self._assistant_bubble)
        self._streaming = False
        self._stream_buffer = ""
        self._assistant_bubble = None

    def _apply_stream_update(self) -> None:
        self._stream_update_job = None
        if not self._streaming:
            self.begin_assistant()
        self._set_plain_text(
            self._assistant_bubble,
            self._stream_buffer,
            text_color=self._role_text_color("assistant"),
            refit=True,
            scroll=False,
        )
        self._schedule_scroll()

    def _destroy_bubble_row(self, bubble: BubbleText) -> None:
        row = bubble
        while row.master is not None and row.master is not self._scroll:
            row = row.master
        if row.master is self._scroll:
            row.destroy()

    def append_tool_call(self, name: str, args: dict) -> None:
        if name == "web_search":
            query = args.get("query", "")
            self._set_tool_status(f"🔍 正在搜索：{query}")
            return
        self._add_meta_line(f"🔧 调用工具: {name}({args})")

    def append_tool_result(self, name: str, content: str) -> None:
        if name == "web_search":
            self.append_search_done(content)
            return
        preview = content[:200] + ("..." if len(content) > 200 else "")
        self._add_meta_line(f"📋 {name} 返回: {preview}")

    def append_search_done(self, raw_result: str) -> None:
        """搜索完成提示（不展示原始摘要）。"""
        count = len(re.findall(r"^\d+\.\s", raw_result, re.MULTILINE))
        if count:
            self._set_tool_status(f"✓ 搜索完成，获取 {count} 条结果，正在汇总…")
        elif "未找到" in raw_result or "搜索失败" in raw_result:
            self._set_tool_status("⚠ 搜索未返回有效结果，正在分析…")
        else:
            self._set_tool_status("✓ 搜索完成，正在汇总…")

    def append_assistant_complete(self, content: str, *, from_cache: bool = False) -> None:
        """直接展示完整助理回复（缓存命中，无流式）。"""
        if from_cache:
            self._add_meta_line("📦 命中搜索缓存，直接返回历史回复")
        bubble = self._add_bubble_row(role="assistant", title="助理")
        render_markdown(bubble, content, text_color=self._role_text_color("assistant"))
        schedule_fit_text_height(
            bubble,
            max_width=self._bubble_max_width("assistant"),
            on_done=self._scroll_to_bottom,
        )

    def append_system(self, content: str) -> None:
        self._add_meta_line(f"⚙️ {content}")

    def append_error(self, content: str) -> None:
        self._add_meta_line(f"❌ 错误: {content}", color="#ef4444")

    def clear(self) -> None:
        if self._stream_update_job is not None:
            self.after_cancel(self._stream_update_job)
            self._stream_update_job = None
        if self._scroll_job is not None:
            self.after_cancel(self._scroll_job)
            self._scroll_job = None
        self._clear_tool_status()
        for child in self._scroll.winfo_children():
            child.destroy()
        self._streaming = False
        self._stream_buffer = ""
        self._assistant_bubble = None

    def _on_scroll_configure(self, event) -> None:
        width = max(200, event.width - self._H_PAD)
        if width == self._max_width:
            return
        self._max_width = width
        self._apply_width_to_bubbles()

    def _apply_width_to_bubbles(self) -> None:
        for bubble in self._iter_bubbles():
            role = getattr(bubble, "_chat_role", "assistant")
            schedule_fit_text_height(bubble, max_width=self._bubble_max_width(role))

    def _iter_bubbles(self):
        for row in self._scroll.winfo_children():
            if row is self._tool_status_row:
                continue
            for outer in row.winfo_children():
                for widget in outer.winfo_children():
                    if isinstance(widget, BubbleText):
                        yield widget

    def _bubble_max_width(self, role: str) -> int:
        ratio = self._USER_MAX_WIDTH_RATIO if role == "user" else self._ASSISTANT_MAX_WIDTH_RATIO
        return max(160, int(self._max_width * ratio))

    def _role_text_color(self, role: str) -> str:
        if role == "user":
            return self._USER_FG
        return resolve_theme_color(self._ASSISTANT_FG)

    def _add_bubble(
        self,
        *,
        role: str,
        title: str,
        content: str,
        use_markdown: bool,
    ) -> None:
        bubble = self._add_bubble_row(role=role, title=title)
        text_color = self._role_text_color(role)
        if use_markdown:
            render_markdown(bubble, content, text_color=text_color)
        else:
            self._set_plain_text(bubble, content, text_color=text_color)
        schedule_fit_text_height(
            bubble,
            max_width=self._bubble_max_width(role),
            on_done=self._scroll_to_bottom,
        )

    def _create_bubble(self, master: ctk.CTkFrame, *, role: str) -> BubbleText:
        max_w = self._bubble_max_width(role)
        if role == "user":
            return BubbleText(
                master,
                fg_color=self._USER_BG,
                text_color=self._USER_FG,
                border_color=self._USER_BORDER,
                corner_radius=CORNER_RADIUS,
                max_width=max_w,
            )
        return BubbleText(
            master,
            fg_color=self._ASSISTANT_BG,
            text_color=self._role_text_color("assistant"),
            border_color=self._ASSISTANT_BORDER,
            corner_radius=CORNER_RADIUS,
            max_width=max_w,
        )

    def _add_bubble_row(self, *, role: str, title: str) -> BubbleText:
        row = ctk.CTkFrame(self._scroll, fg_color="transparent")
        row.pack(fill="x", pady=(10, 2))

        is_user = role == "user"
        anchor = "e" if is_user else "w"
        side = "right" if is_user else "left"

        outer = ctk.CTkFrame(row, fg_color="transparent")
        outer.pack(side=side, anchor=anchor, padx=(16, 12) if is_user else (12, 16))

        ctk.CTkLabel(
            outer,
            text=f"{'👤' if is_user else '🤖'} {title}",
            font=ctk.CTkFont(size=11),
            text_color=self._ROLE_LABEL_FG,
            anchor=anchor,
        ).pack(anchor=anchor, padx=4, pady=(0, 4))

        bubble = self._create_bubble(outer, role=role)
        bubble._chat_role = role
        bubble.pack(anchor=anchor)
        return bubble

    def _set_tool_status(self, text: str) -> None:
        """复用同一行展示工具进度，避免多次插入引发布局跳动。"""
        if self._tool_status_label is None:
            self._tool_status_row = ctk.CTkFrame(self._scroll, fg_color="transparent")
            self._tool_status_row.pack(fill="x", pady=(6, 0))
            self._tool_status_label = ctk.CTkLabel(
                self._tool_status_row,
                text=text,
                font=ctk.CTkFont(size=12),
                text_color=self._TOOL_FG,
                anchor="w",
                justify="left",
                wraplength=max(200, self._max_width),
            )
            self._tool_status_label.pack(anchor="w", padx=12, fill="x")
        else:
            self._tool_status_label.configure(text=text)
        self._schedule_scroll()

    def _clear_tool_status(self) -> None:
        if self._tool_status_row is not None:
            self._tool_status_row.destroy()
        self._tool_status_row = None
        self._tool_status_label = None

    def _add_meta_line(self, text: str, *, color: str | tuple[str, str] | None = None) -> None:
        row = ctk.CTkFrame(self._scroll, fg_color="transparent")
        row.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(
            row,
            text=text,
            font=ctk.CTkFont(size=12),
            text_color=color or self._TOOL_FG,
            anchor="w",
            justify="left",
            wraplength=max(200, self._max_width),
        ).pack(anchor="w", padx=12, fill="x")
        self._schedule_scroll()

    def _set_plain_text(
        self,
        bubble: BubbleText | None,
        content: str,
        *,
        text_color: str | None = None,
        refit: bool = True,
        scroll: bool = True,
    ) -> None:
        if bubble is None:
            return
        set_plain_text_content(bubble, content, text_color=text_color)
        if refit:
            role = getattr(bubble, "_chat_role", "assistant")
            fit_bubble_size(bubble, max_width=self._bubble_max_width(role))
        if scroll:
            self._schedule_scroll()

    def _schedule_scroll(self) -> None:
        if self._scroll_job is not None:
            self.after_cancel(self._scroll_job)
        self._scroll_job = self.after(self._SCROLL_DEBOUNCE_MS, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        self._scroll_job = None
        self.update_idletasks()
        canvas = getattr(self._scroll, "_parent_canvas", None)
        if canvas is not None:
            canvas.yview_moveto(1.0)
