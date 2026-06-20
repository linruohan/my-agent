"""聊天气泡正文：CTkFrame + tk.Text，支持可靠的高度与宽度自适应。"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from typing import Any

import customtkinter as ctk


def _resolve_color(color: str | tuple[str, str]) -> str:
    if isinstance(color, tuple):
        return color[1] if ctk.get_appearance_mode().lower() == "dark" else color[0]
    return color


class BubbleText(ctk.CTkFrame):
    """带圆角背景的消息正文区域。"""

    _MIN_WIDTH = 80
    _PAD_X = 24

    def __init__(
        self,
        master: Any,
        *,
        fg_color: str | tuple[str, str],
        text_color: str | None = None,
        max_width: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color=fg_color, corner_radius=12, **kwargs)
        bg = _resolve_color(fg_color)
        if text_color is None:
            text_color = "#ffffff" if ctk.get_appearance_mode().lower() == "dark" else "#1a1a1a"

        self._max_width = max_width or 640
        self._font = tkfont.Font(family="Segoe UI", size=13)

        self._text = tk.Text(
            self,
            wrap="word",
            width=16,
            height=3,
            font=self._font,
            borderwidth=0,
            highlightthickness=0,
            bg=bg,
            fg=text_color,
            insertbackground=text_color,
            padx=10,
            pady=8,
            cursor="arrow",
        )
        self._text.pack(fill="both", expand=True)
        self._md_images: list[Any] = []
        self._md_extra_lines = 0
        self.set_readonly()

    @property
    def text_widget(self) -> tk.Text:
        return self._text

    def set_max_width(self, pixels: int) -> None:
        self._max_width = max(self._MIN_WIDTH + self._PAD_X, pixels)
        self.fit_width()

    def fit_width(self) -> None:
        """内容未超宽时收缩；超过 max_width 时按 max_width 换行。"""
        tb = self._text
        tb.update_idletasks()
        content = tb.get("1.0", "end-1c")
        if not content.strip():
            self.configure(width=self._MIN_WIDTH)
            tb.configure(width=8)
            return

        char_w = max(self._font.measure("0"), 1)
        longest_px = max((self._font.measure(line) for line in content.splitlines()), default=0)
        natural = longest_px + self._PAD_X
        target = min(max(natural, self._MIN_WIDTH), self._max_width)
        tb.configure(width=max(8, target // char_w))
        self.configure(width=target)

    def set_readonly(self) -> None:
        self._text.configure(state="disabled")

    def set_editable(self) -> None:
        self._text.configure(state="normal")
