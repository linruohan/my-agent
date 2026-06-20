from __future__ import annotations

import re
from datetime import datetime

import customtkinter as ctk

from src.ui.bubble_text import BubbleText, resolve_theme_color
from src.ui.markdown_render import (
    fit_bubble_size,
    render_markdown,
    schedule_fit_text_height,
    set_plain_text_content,
)
from src.ui.theme import (
    ASSISTANT_BG,
    ASSISTANT_BORDER,
    ASSISTANT_FG,
    ASSISTANT_MAX_WIDTH_RATIO,
    AVATAR_ASSISTANT_BG,
    AVATAR_RADIUS,
    AVATAR_SIZE,
    AVATAR_USER_BG,
    BUBBLE_RADIUS,
    CAPTION_FG,
    CHAT_BG,
    CHIP_RADIUS,
    FONT_CAPTION,
    FONT_META,
    MESSAGE_GAP,
    META_BG,
    META_ERROR,
    META_FG,
    META_INFO,
    META_SUCCESS,
    SIDE_INSET,
    USER_BUBBLE,
    USER_BUBBLE_BORDER,
    USER_FG,
    USER_MAX_WIDTH_RATIO,
    resolve,
)


def normalize_user_message(text: str) -> str:
    from src.ui.markdown_render import compact_bubble_content

    return compact_bubble_content(text)


class ChatPanel(ctk.CTkFrame):
    """聊天消息展示区：Markdown 渲染，用户右对齐，助理左对齐。"""

    _H_PAD = 24
    _STREAM_DEBOUNCE_MS = 80
    _SCROLL_DEBOUNCE_MS = 60

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._chat_surface = ctk.CTkFrame(
            self,
            fg_color=resolve(CHAT_BG),
            corner_radius=10,
        )
        self._chat_surface.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self._chat_surface.grid_rowconfigure(0, weight=1)
        self._chat_surface.grid_columnconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(self._chat_surface, fg_color="transparent")
        self._scroll.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self._scroll.bind("<Configure>", self._on_scroll_configure)

        self._streaming = False
        self._stream_buffer = ""
        self._assistant_bubble: BubbleText | None = None
        self._max_width = 640

        self._stream_update_job: str | None = None
        self._scroll_job: str | None = None
        self._tool_status_row: ctk.CTkFrame | None = None
        self._tool_status_capsule: ctk.CTkFrame | None = None
        self._tool_status_label: ctk.CTkLabel | None = None

    def append_user(self, content: str) -> None:
        content = normalize_user_message(content)
        if not content:
            return
        self._clear_tool_status()
        self._add_bubble(role="user", content=content, use_markdown=True)

    def begin_assistant(self) -> None:
        self._streaming = True
        self._stream_buffer = ""
        self._clear_tool_status()
        self._assistant_bubble = self._add_bubble_row(role="assistant")

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

    @property
    def assistant_stream_buffer(self) -> str:
        return self._stream_buffer

    def reset_assistant_for_tool(self) -> None:
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
            self._set_tool_status(f"🔍 正在搜索：{query}", accent=META_INFO)
            return
        self._add_meta_capsule(f"🔧 调用工具: {name}({args})")

    def append_tool_result(self, name: str, content: str) -> None:
        if name == "web_search":
            self.append_search_done(content)
            return
        preview = content[:200] + ("..." if len(content) > 200 else "")
        self._add_meta_capsule(f"📋 {name} 返回: {preview}")

    def append_search_done(self, raw_result: str) -> None:
        count = len(re.findall(r"^\d+\.\s", raw_result, re.MULTILINE))
        if count:
            self._set_tool_status(f"✓ 搜索完成，获取 {count} 条结果，正在汇总…", accent=META_SUCCESS)
        elif "未找到" in raw_result or "搜索失败" in raw_result:
            self._set_tool_status("⚠ 搜索未返回有效结果，正在分析…", accent=META_ERROR)
        else:
            self._set_tool_status("✓ 搜索完成，正在汇总…", accent=META_SUCCESS)

    def append_assistant_complete(self, content: str, *, from_cache: bool = False) -> None:
        if from_cache:
            self._add_meta_capsule("📦 命中搜索缓存，直接返回历史回复", accent=META_INFO)
        bubble = self._add_bubble_row(role="assistant")
        render_markdown(bubble, content, text_color=self._role_text_color("assistant"))
        schedule_fit_text_height(
            bubble,
            max_width=self._bubble_max_width("assistant"),
            on_done=self._scroll_to_bottom,
        )

    def append_system(self, content: str) -> None:
        self._add_meta_capsule(f"⚙️ {content}")

    def append_error(self, content: str) -> None:
        self._add_meta_capsule(f"❌ 错误: {content}", accent=META_ERROR)

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
            for widget in row.winfo_children():
                yield from self._walk_bubbles(widget)

    def _walk_bubbles(self, widget):
        if isinstance(widget, BubbleText):
            yield widget
            return
        for child in widget.winfo_children():
            yield from self._walk_bubbles(child)

    def _bubble_max_width(self, role: str) -> int:
        ratio = USER_MAX_WIDTH_RATIO if role == "user" else ASSISTANT_MAX_WIDTH_RATIO
        return max(160, int(self._max_width * ratio))

    def _role_text_color(self, role: str) -> str:
        if role == "user":
            return USER_FG
        return resolve_theme_color(ASSISTANT_FG)

    @staticmethod
    def _now_label() -> str:
        return datetime.now().strftime("%H:%M")

    def _make_avatar(self, master: ctk.CTkFrame, *, role: str) -> ctk.CTkFrame:
        bg = resolve(AVATAR_USER_BG if role == "user" else AVATAR_ASSISTANT_BG)
        frame = ctk.CTkFrame(
            master,
            width=AVATAR_SIZE,
            height=AVATAR_SIZE,
            corner_radius=AVATAR_RADIUS,
            fg_color=bg,
        )
        frame.pack_propagate(False)
        emoji = "👤" if role == "user" else "🤖"
        ctk.CTkLabel(
            frame,
            text=emoji,
            font=ctk.CTkFont(size=15),
            text_color=resolve(CAPTION_FG),
        ).place(relx=0.5, rely=0.5, anchor="center")
        return frame

    def _add_bubble(self, *, role: str, content: str, use_markdown: bool) -> None:
        bubble = self._add_bubble_row(role=role)
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
                fg_color=USER_BUBBLE,
                text_color=USER_FG,
                border_color=USER_BUBBLE_BORDER,
                corner_radius=BUBBLE_RADIUS,
                max_width=max_w,
            )
        return BubbleText(
            master,
            fg_color=ASSISTANT_BG,
            text_color=self._role_text_color("assistant"),
            border_color=ASSISTANT_BORDER,
            corner_radius=BUBBLE_RADIUS,
            max_width=max_w,
        )

    def _add_bubble_row(self, *, role: str) -> BubbleText:
        row = ctk.CTkFrame(self._scroll, fg_color="transparent")
        row.pack(fill="x", pady=(MESSAGE_GAP, 2))

        is_user = role == "user"
        side = "right" if is_user else "left"
        anchor = "e" if is_user else "w"
        padx = (SIDE_INSET, 10) if is_user else (10, SIDE_INSET)

        outer = ctk.CTkFrame(row, fg_color="transparent")
        outer.pack(side=side, anchor=anchor, padx=padx)

        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.pack(anchor=anchor)

        if is_user:
            content_col = ctk.CTkFrame(body, fg_color="transparent")
            content_col.pack(side="right")
            ctk.CTkLabel(
                content_col,
                text=f"我 · {self._now_label()}",
                font=ctk.CTkFont(size=FONT_CAPTION),
                text_color=resolve(CAPTION_FG),
                anchor="e",
            ).pack(anchor="e", pady=(0, 4))
            bubble = self._create_bubble(content_col, role=role)
            bubble.pack(anchor="e")
            avatar = self._make_avatar(body, role=role)
            avatar.pack(side="right", padx=(10, 0), anchor="n", pady=(18, 0))
        else:
            avatar = self._make_avatar(body, role=role)
            avatar.pack(side="left", padx=(0, 10), anchor="n", pady=(18, 0))
            content_col = ctk.CTkFrame(body, fg_color="transparent")
            content_col.pack(side="left")
            ctk.CTkLabel(
                content_col,
                text=f"助理 · {self._now_label()}",
                font=ctk.CTkFont(size=FONT_CAPTION),
                text_color=resolve(CAPTION_FG),
                anchor="w",
            ).pack(anchor="w", pady=(0, 4))
            bubble = self._create_bubble(content_col, role=role)
            bubble.pack(anchor="w")

        bubble._chat_role = role
        return bubble

    def _add_meta_capsule(
        self,
        text: str,
        *,
        accent: str | tuple[str, str] | None = None,
    ) -> None:
        row = ctk.CTkFrame(self._scroll, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))
        holder = ctk.CTkFrame(row, fg_color="transparent")
        holder.pack(fill="x")
        capsule = ctk.CTkFrame(
            holder,
            fg_color=resolve(META_BG),
            corner_radius=CHIP_RADIUS,
        )
        capsule.pack(anchor="center", pady=2)
        fg = resolve(accent) if accent else resolve(META_FG)
        ctk.CTkLabel(
            capsule,
            text=text,
            font=ctk.CTkFont(size=FONT_META),
            text_color=fg,
            wraplength=max(240, self._max_width - 80),
            justify="center",
        ).pack(padx=14, pady=5)
        self._schedule_scroll()

    def _set_tool_status(
        self,
        text: str,
        *,
        accent: str | tuple[str, str] | None = None,
    ) -> None:
        fg = resolve(accent) if accent else resolve(META_FG)
        if self._tool_status_label is None:
            self._tool_status_row = ctk.CTkFrame(self._scroll, fg_color="transparent")
            self._tool_status_row.pack(fill="x", pady=(8, 0))
            holder = ctk.CTkFrame(self._tool_status_row, fg_color="transparent")
            holder.pack(fill="x")
            self._tool_status_capsule = ctk.CTkFrame(
                holder,
                fg_color=resolve(META_BG),
                corner_radius=CHIP_RADIUS,
            )
            self._tool_status_capsule.pack(anchor="center", pady=2)
            self._tool_status_label = ctk.CTkLabel(
                self._tool_status_capsule,
                text=text,
                font=ctk.CTkFont(size=FONT_META),
                text_color=fg,
                wraplength=max(240, self._max_width - 80),
                justify="center",
            )
            self._tool_status_label.pack(padx=14, pady=5)
        else:
            self._tool_status_label.configure(text=text, text_color=fg)
        self._schedule_scroll()

    def _clear_tool_status(self) -> None:
        if self._tool_status_row is not None:
            self._tool_status_row.destroy()
        self._tool_status_row = None
        self._tool_status_capsule = None
        self._tool_status_label = None

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
