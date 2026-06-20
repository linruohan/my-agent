from __future__ import annotations

import customtkinter as ctk


class ChatPanel(ctk.CTkFrame):
    """聊天消息展示区。"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._text = ctk.CTkTextbox(self, wrap="word", font=ctk.CTkFont(size=14))
        self._text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self._text.configure(state="disabled")
        self._streaming = False
        self._stream_buffer = ""

    def append_user(self, content: str) -> None:
        self._append(f"\n\n👤 你\n{content}\n", "user")

    def begin_assistant(self) -> None:
        self._streaming = True
        self._stream_buffer = ""
        self._append("\n\n🤖 助理\n", "assistant")

    def append_token(self, token: str) -> None:
        if not self._streaming:
            self.begin_assistant()
        self._stream_buffer += token
        self._append(token, "stream")

    def end_assistant(self) -> None:
        self._streaming = False
        self._append("\n", "assistant")

    def append_tool_call(self, name: str, args: dict) -> None:
        self._append(f"\n🔧 调用工具: {name}({args})\n", "tool")

    def append_tool_result(self, name: str, content: str) -> None:
        preview = content[:200] + ("..." if len(content) > 200 else "")
        self._append(f"📋 {name} 返回: {preview}\n", "tool")

    def append_system(self, content: str) -> None:
        self._append(f"\n⚙️ {content}\n", "system")

    def append_error(self, content: str) -> None:
        self._append(f"\n❌ 错误: {content}\n", "error")

    def clear(self) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")

    def _append(self, text: str, tag: str = "") -> None:
        self._text.configure(state="normal")
        self._text.insert("end", text)
        self._text.configure(state="disabled")
        self._text.see("end")
