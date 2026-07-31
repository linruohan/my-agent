"""WebView 聊天事件桥：Python -> JS。"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

from loguru import logger

WindowGetter = Callable[[], Any]

_TOKEN_FLUSH_CHARS = 48
_TOKEN_FLUSH_SEC = 0.05


class WebChatBridge:
    """替代 ChatPanel，通过 evaluate_js 驱动前端 ChatUI。"""

    def __init__(self, get_window: WindowGetter, *, on_event: Callable[[dict[str, Any]], None] | None = None) -> None:
        self._get_window = get_window
        self._on_event = on_event
        self._stream_buffer = ""
        self._streaming = False
        self._turn_started_at: float | None = None
        self._pending_token_ui = ""
        self._last_token_flush = 0.0

    @property
    def assistant_stream_buffer(self) -> str:
        return self._stream_buffer

    def _emit(self, event: dict[str, Any]) -> None:
        if self._on_event:
            try:
                self._on_event(event)
            except Exception as exc:
                logger.warning("聊天事件持久化回调失败: {}", exc)
        window = self._get_window()
        if window is None:
            return
        payload = json.dumps(event, ensure_ascii=False)
        try:
            window.evaluate_js(f"window.ChatApp.handleEvent({payload})")
        except Exception as exc:
            logger.warning("推送聊天事件到 WebView 失败: {}", exc)

    def load_history(self, events: list[dict[str, Any]]) -> None:
        """批量回放会话历史（单次 JS 调用）。

        优先 ChatApp.loadHistory（React UI），回退 ChatUI.loadHistory（旧版）。
        """
        window = self._get_window()
        if window is None:
            return
        payload = json.dumps(events, ensure_ascii=False)
        script = (
            "(function(p){"
            "var fn=(window.ChatApp&&window.ChatApp.loadHistory)"
            "||(window.ChatUI&&window.ChatUI.loadHistory);"
            "if(fn)fn(p);"
            "})("
            f"{payload})"
        )
        try:
            window.evaluate_js(script)
        except Exception as exc:
            logger.warning("批量加载会话历史失败: {}", exc)

    def _elapsed_ms(self) -> int | None:
        if self._turn_started_at is None:
            return None
        return max(0, int((time.perf_counter() - self._turn_started_at) * 1000))

    def clear_turn_timer(self) -> None:
        self._turn_started_at = None

    def append_user(
        self,
        content: str,
        *,
        images: list[dict[str, Any]] | None = None,
        track_turn: bool = True,
    ) -> None:
        if track_turn:
            self._turn_started_at = time.perf_counter()
        event: dict[str, Any] = {"type": "user", "content": content}
        if images:
            event["images"] = images
        self._emit(event)

    def begin_assistant(self, *, initial: str = "") -> None:
        self.flush_tokens()
        self._streaming = True
        self._stream_buffer = initial
        event: dict[str, Any] = {"type": "assistant_start"}
        if initial:
            event["content"] = initial
        self._emit(event)

    def begin_assistant_progress(self, text: str) -> None:
        self.begin_assistant(initial=text)

    def append_token(self, token: str) -> None:
        if not token:
            return
        self._stream_buffer += token
        if not self._streaming:
            self.begin_assistant()
        self._pending_token_ui += token
        self._maybe_flush_tokens()

    def _maybe_flush_tokens(self, *, force: bool = False) -> None:
        if not self._pending_token_ui:
            return
        now = time.perf_counter()
        if not force and len(self._pending_token_ui) < _TOKEN_FLUSH_CHARS:
            if self._last_token_flush and (now - self._last_token_flush) < _TOKEN_FLUSH_SEC:
                return
        chunk = self._pending_token_ui
        self._pending_token_ui = ""
        self._last_token_flush = now
        self._emit({"type": "assistant_token", "content": chunk})

    def flush_tokens(self) -> None:
        """将缓冲中的流式 token 推送到前端（轮询批次结束或回合结束时调用）。"""
        self._maybe_flush_tokens(force=True)

    def end_assistant(self) -> None:
        self.flush_tokens()
        event: dict[str, Any] = {"type": "assistant_end", "content": self._stream_buffer}
        elapsed = self._elapsed_ms()
        if elapsed is not None:
            event["elapsed_ms"] = elapsed
        self._emit(event)
        self._streaming = False
        self._stream_buffer = ""
        self._turn_started_at = None

    def reset_assistant_for_tool(self) -> None:
        self.flush_tokens()
        self._streaming = False
        self._stream_buffer = ""
        self._pending_token_ui = ""
        self._emit({"type": "assistant_reset"})

    def append_tool_call(self, name: str, args: dict) -> None:
        if name == "web_search":
            query = args.get("query", "")
            self._emit(
                {
                    "type": "tool_status",
                    "content": f"🔍 正在搜索：{query}",
                    "accent": "info",
                }
            )
            return
        self._emit({"type": "meta", "content": f"🔧 调用工具: {name}({args})"})

    def append_tool_result(self, name: str, content: str) -> None:
        if name == "web_search":
            self.append_search_done(content)
            return
        preview = content[:200] + ("..." if len(content) > 200 else "")
        self._emit({"type": "meta", "content": f"📋 {name} 返回: {preview}"})

    def append_search_done(self, raw_result: str) -> None:
        count = len(re.findall(r"^\d+\.\s", raw_result, re.MULTILINE))
        if count:
            self._emit(
                {
                    "type": "tool_status",
                    "content": f"✓ 搜索完成，获取 {count} 条结果，正在汇总…",
                    "accent": "success",
                }
            )
        elif "未找到" in raw_result or "搜索失败" in raw_result:
            self._emit(
                {
                    "type": "tool_status",
                    "content": "⚠ 搜索未返回有效结果，正在分析…",
                    "accent": "error",
                }
            )
        else:
            self._emit(
                {
                    "type": "tool_status",
                    "content": "✓ 搜索完成，正在汇总…",
                    "accent": "success",
                }
            )

    def append_assistant_complete(
        self,
        content: str,
        *,
        from_cache: bool = False,
        content_format: str = "markdown",
    ) -> None:
        self.flush_tokens()
        if from_cache:
            pass
        self._stream_buffer = content
        event: dict[str, Any] = {
            "type": "assistant_end",
            "content": content,
            "content_format": content_format,
        }
        elapsed = self._elapsed_ms()
        if elapsed is not None:
            event["elapsed_ms"] = elapsed
        self._emit(event)
        self._stream_buffer = ""
        self._streaming = False
        self._turn_started_at = None

    def append_system(self, content: str) -> None:
        self._emit({"type": "meta", "content": f"⚙️ {content}"})

    def append_error(self, content: str) -> None:
        self._emit({"type": "meta", "content": f"❌ 错误: {content}", "accent": "error"})

    def set_tool_status(self, content: str, *, accent: str | None = None) -> None:
        event: dict[str, Any] = {"type": "tool_status", "content": content}
        if accent:
            event["accent"] = accent
        self._emit(event)

    def clear_tool_status(self) -> None:
        self._emit({"type": "tool_status", "content": ""})

    def clear(self) -> None:
        self._pending_token_ui = ""
        self._streaming = False
        self._stream_buffer = ""
        self._turn_started_at = None
        self._emit({"type": "clear"})

    def set_status(self, text: str) -> None:
        self._emit({"type": "status", "text": text})

    def set_running(self, running: bool) -> None:
        self._emit({"type": "running", "running": running})

    def show_approval(self, description: str) -> None:
        self._emit({"type": "approval", "description": description})

    def apply_theme(self, variables: dict[str, str]) -> None:
        self._emit({"type": "theme", "variables": variables})
