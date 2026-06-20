from __future__ import annotations

import re

import customtkinter as ctk

from src.ui.bubble_text import BubbleText
from src.ui.markdown_render import render_markdown, schedule_fit_text_height, set_plain_text_content


class ChatPanel(ctk.CTkFrame):
    """聊天消息展示区：Markdown 渲染，用户右对齐，助理左对齐。"""

    _USER_BG = "#2563eb"
    _USER_FG = "#ffffff"
    _ASSISTANT_BG = ("#e8eaed", "#2d2d2d")
    _TOOL_FG = ("gray45", "gray55")
    _H_PAD = 24

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

    def append_user(self, content: str) -> None:
        self._add_bubble(
            role="user",
            title="你",
            content=content,
            use_markdown=True,
        )

    def begin_assistant(self) -> None:
        self._streaming = True
        self._stream_buffer = ""
        self._assistant_bubble = self._add_bubble_row(role="assistant", title="助理")

    def append_token(self, token: str) -> None:
        if not self._streaming:
            self.begin_assistant()
        self._stream_buffer += token
        self._set_plain_text(self._assistant_bubble, self._stream_buffer)

    def end_assistant(self) -> None:
        bubble = self._assistant_bubble
        if bubble:
            if self._stream_buffer:
                render_markdown(bubble, self._stream_buffer)
            schedule_fit_text_height(bubble, max_width=self._max_width, on_done=self._scroll_to_bottom)
        self._streaming = False
        self._stream_buffer = ""
        self._assistant_bubble = None

    def reset_assistant_for_tool(self) -> None:
        """工具调用前移除规划语气泡，后续 token 将开启新的汇总回复。"""
        if self._assistant_bubble is not None:
            self._destroy_bubble_row(self._assistant_bubble)
        self._streaming = False
        self._stream_buffer = ""
        self._assistant_bubble = None

    def _destroy_bubble_row(self, bubble: BubbleText) -> None:
        row = bubble
        while row.master is not None and row.master is not self._scroll:
            row = row.master
        if row.master is self._scroll:
            row.destroy()

    def append_tool_call(self, name: str, args: dict) -> None:
        if name == "web_search":
            query = args.get("query", "")
            self._add_meta_line(f"🔍 正在搜索：{query}")
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
            self._add_meta_line(f"✓ 搜索完成，获取 {count} 条结果，正在汇总…")
        elif "未找到" in raw_result or "搜索失败" in raw_result:
            self._add_meta_line("⚠ 搜索未返回有效结果，正在分析…")
        else:
            self._add_meta_line("✓ 搜索完成，正在汇总…")

    def append_system(self, content: str) -> None:
        self._add_meta_line(f"⚙️ {content}")

    def append_error(self, content: str) -> None:
        self._add_meta_line(f"❌ 错误: {content}", color="#ef4444")

    def clear(self) -> None:
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
            schedule_fit_text_height(bubble, max_width=self._max_width)

    def _iter_bubbles(self):
        for row in self._scroll.winfo_children():
            for outer in row.winfo_children():
                for widget in outer.winfo_children():
                    if isinstance(widget, BubbleText):
                        yield widget

    def _add_bubble(
        self,
        *,
        role: str,
        title: str,
        content: str,
        use_markdown: bool,
    ) -> None:
        bubble = self._add_bubble_row(role=role, title=title)
        if use_markdown:
            fg = self._USER_FG if role == "user" else None
            render_markdown(bubble, content, text_color=fg)
        else:
            self._set_plain_text(bubble, content, text_color=self._USER_FG if role == "user" else None)
        schedule_fit_text_height(bubble, max_width=self._max_width)
        self._scroll_to_bottom()

    def _create_bubble(self, master: ctk.CTkFrame, *, role: str) -> BubbleText:
        if role == "user":
            return BubbleText(
                master,
                fg_color=self._USER_BG,
                text_color=self._USER_FG,
                max_width=self._max_width,
            )
        return BubbleText(
            master,
            fg_color=self._ASSISTANT_BG,
            max_width=self._max_width,
        )

    def _add_bubble_row(self, *, role: str, title: str) -> BubbleText:
        row = ctk.CTkFrame(self._scroll, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))

        is_user = role == "user"
        anchor = "e" if is_user else "w"
        side = "right" if is_user else "left"

        outer = ctk.CTkFrame(row, fg_color="transparent")
        outer.pack(side=side, anchor=anchor, padx=12)

        label = ctk.CTkLabel(
            outer,
            text=f"{'👤' if is_user else '🤖'} {title}",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray60"),
            anchor=anchor,
        )
        label.pack(anchor=anchor, padx=4, pady=(0, 2))

        bubble = self._create_bubble(outer, role=role)
        bubble.pack(anchor=anchor)
        return bubble

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
        self._scroll_to_bottom()

    def _set_plain_text(
        self,
        bubble: BubbleText | None,
        content: str,
        *,
        text_color: str | None = None,
    ) -> None:
        if bubble is None:
            return
        set_plain_text_content(bubble, content, text_color=text_color)
        schedule_fit_text_height(bubble, max_width=self._max_width)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        self.update_idletasks()
        canvas = getattr(self._scroll, "_parent_canvas", None)
        if canvas is not None:
            canvas.yview_moveto(1.0)
