"""用户消息发送与意图路由。"""

from __future__ import annotations

import threading
from typing import Any

from loguru import logger

from src.ui.input import (
    INTENT_LINK,
    INTENT_OCR,
    INTENT_SEARCH,
    INTENT_SLASH_CACHE,
    INTENT_SLASH_NOTE,
    INTENT_SLASH_OCR,
    INTENT_SLASH_SKILL,
    INTENT_SLASH_TASK,
    INTENT_SLASH_WEATHER,
    INTENT_WEATHER,
    compose_user_message,
    has_sendable_content,
    resolve_input_intent,
)
from src.ui.input import append_history
from src.ui.input import build_image_previews
from src.ui.message_utils import normalize_user_message
from src.ui.ocr import ocr_progress_text


class RouterMixin:
    """消息发送入口与意图分发。"""

    def send_message(self, payload: dict[str, Any]) -> bool:
        if self._is_busy():
            return False

        text = str(payload.get("text", ""))
        attachments = list(payload.get("attachments") or [])

        if not has_sendable_content(text, attachments):
            self.chat.append_error("请输入内容或添加附件")
            return False

        display_text = normalize_user_message(text)
        images = build_image_previews(attachments)
        self.chat.append_user(display_text, images=images)
        append_history(display_text)

        self._compose_cancel.clear()
        self._compose_busy = True
        self.chat.set_running(True)

        threading.Thread(
            target=self._process_send_message,
            args=(text, attachments),
            daemon=True,
            name="compose-send",
        ).start()
        return True

    @staticmethod
    def _should_use_search_pipeline(
        composed: dict[str, Any],
        attachments: list[dict[str, Any]],
    ) -> bool:
        """已由 resolve_input_intent 替代，保留供测试/兼容。"""
        if composed.get("ocr_only"):
            return False
        if any(att.get("type") in ("file", "link") for att in attachments):
            return False
        user_text = str(composed.get("user_text") or "").strip()
        message = str(composed.get("message") or "").strip()
        if attachments and message != user_text:
            return False
        return bool(user_text or message)

    def _lookup_search_cache(self, *queries: str) -> str | None:
        seen: set[str] = set()
        for query in queries:
            q = (query or "").strip()
            if not q or q in seen:
                continue
            seen.add(q)
            hit = self._search_cache.lookup(q)
            if hit:
                return hit
        return None

    def _process_send_message(self, text: str, attachments: list[dict[str, Any]]) -> None:
        try:
            if self._compose_cancel.is_set():
                return

            intent = resolve_input_intent(text, attachments, llm=self._llm)
            logger.info("[intent] kind={} reason={}", intent.kind, intent.reason)

            if intent.kind == INTENT_SLASH_NOTE:
                self._handle_slash_note(intent)
                return

            if intent.kind == INTENT_SLASH_CACHE:
                self._handle_slash_cache(intent)
                return

            if intent.kind == INTENT_SLASH_TASK:
                self._handle_slash_task(intent)
                return

            if intent.kind == INTENT_SLASH_SKILL:
                self._handle_slash_skill(intent, text)
                return

            if intent.kind in (INTENT_OCR, INTENT_SLASH_OCR):
                self._handle_ocr_intent(text, attachments, intent)
                return

            if intent.kind in (INTENT_WEATHER, INTENT_SLASH_WEATHER):
                self._handle_weather_intent(intent, text)
                return

            if intent.kind == INTENT_LINK:
                self._start_link_summarize_turn(intent)
                return

            search_query = (intent.search_query or normalize_user_message(text or "")).strip()
            if intent.kind == INTENT_SEARCH and search_query and not attachments:
                cached = self._lookup_search_cache(search_query)
                if cached:
                    self._deliver_cached_search(search_query, cached)
                    return

            if intent.kind == INTENT_SEARCH and search_query:
                self._start_search_turn(search_query)
                return

            has_images = any(att.get("type") == "image" for att in attachments)
            ocr_progress = False
            if has_images:
                ocr_progress = True
                self.chat.begin_assistant_progress(ocr_progress_text())

            if self._compose_cancel.is_set():
                return

            composed = compose_user_message(text, attachments)
            if self._compose_cancel.is_set():
                return

            if not composed.get("ok"):
                if ocr_progress:
                    self.chat.append_assistant_complete(f"识别失败：{composed.get('error', '消息处理失败')}")
                else:
                    self.chat.append_error(composed.get("error", "消息处理失败"))
                return

            for warn in composed.get("errors") or []:
                self.chat.append_system(warn)

            if self._compose_cancel.is_set():
                return

            message = composed["message"]
            if not self.runner.graph:
                if ocr_progress:
                    self.chat.append_assistant_complete("Agent 未就绪，请检查 LLM 配置与 API Key。")
                else:
                    self.chat.append_error("Agent 未就绪，请检查 LLM 配置与 API Key。")
                return

            if ocr_progress:
                self.chat.reset_assistant_for_tool()

            if self._compose_cancel.is_set():
                return

            self._start_agent_turn(message)
        finally:
            if not self._running:
                self._compose_busy = False
                if not self._compose_cancel.is_set():
                    self.chat.set_running(False)
