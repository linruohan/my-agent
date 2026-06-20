from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk


class ConfirmDialog(ctk.CTkToplevel):
    """敏感操作确认对话框。"""

    def __init__(
        self,
        master,
        title: str,
        description: str,
        on_confirm: Callable[[], None],
        on_cancel: Callable[[], None] | None = None,
    ):
        super().__init__(master)
        self.title("操作确认")
        self.geometry("420x280")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self._on_confirm = on_confirm
        self._on_cancel = on_cancel

        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=16, weight="bold")).pack(
            pady=(20, 8), padx=20, anchor="w"
        )
        text = ctk.CTkTextbox(self, height=120, wrap="word")
        text.pack(fill="both", expand=True, padx=20, pady=8)
        text.insert("1.0", description)
        text.configure(state="disabled")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkButton(
            btn_frame, text="取消", width=100, fg_color="gray40", command=self._cancel
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            btn_frame, text="确认执行", width=100, command=self._confirm
        ).pack(side="right")

    def _confirm(self) -> None:
        self.grab_release()
        self.destroy()
        self._on_confirm()

    def _cancel(self) -> None:
        self.grab_release()
        self.destroy()
        if self._on_cancel:
            self._on_cancel()
