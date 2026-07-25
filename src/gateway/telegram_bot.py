"""Telegram Bot 长轮询（Gateway 通道）。"""

from __future__ import annotations

import threading
from typing import Callable

import httpx
from loguru import logger

from src.gateway.inbox import GatewayInbox


class TelegramGateway:
    API = "https://api.telegram.org/bot{token}/{method}"

    def __init__(
        self,
        inbox: GatewayInbox,
        *,
        bot_token: str,
        allowed_chat_ids: set[str] | None = None,
        poll_interval: float = 2.0,
        on_outbound: Callable[[str, str, str], None] | None = None,
    ) -> None:
        self.inbox = inbox
        self.bot_token = bot_token
        self.allowed_chat_ids = allowed_chat_ids or set()
        self.poll_interval = poll_interval
        self.on_outbound = on_outbound
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._offset = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="gateway-telegram")
        self._thread.start()
        logger.info("Gateway Telegram 轮询已启动")

    def stop(self) -> None:
        self._stop.set()

    def send_message(self, chat_id: str, text: str) -> bool:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    self.API.format(token=self.bot_token, method="sendMessage"),
                    json={"chat_id": chat_id, "text": text[:4000]},
                )
                resp.raise_for_status()
                return True
        except Exception as exc:
            logger.warning("Telegram 发送失败: {}", exc)
            return False

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._poll_once()
            except Exception:
                logger.exception("Telegram 轮询异常")
            self._stop.wait(self.poll_interval)

    def _poll_once(self) -> None:
        with httpx.Client(timeout=35) as client:
            resp = client.get(
                self.API.format(token=self.bot_token, method="getUpdates"),
                params={"offset": self._offset, "timeout": 25},
            )
            resp.raise_for_status()
            data = resp.json()
        if not data.get("ok"):
            return
        for item in data.get("result") or []:
            self._offset = max(self._offset, int(item.get("update_id", 0)) + 1)
            self.ingest_update(item)

    def ingest_update(self, item: dict) -> bool:
        """处理单条 Telegram update（便于单测，无网络）。成功入站返回 True。"""
        message = item.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id", ""))
        text = str(message.get("text") or "").strip()
        if not chat_id or not text:
            return False
        if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
            logger.debug("忽略未授权 Telegram chat_id={}", chat_id)
            return False
        self.inbox.push_inbound(
            "telegram",
            chat_id,
            text,
            meta={"update_id": item.get("update_id")},
        )
        return True
