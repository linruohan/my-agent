"""Slack Socket Mode Gateway。"""

from __future__ import annotations

import asyncio
import json

import httpx
from loguru import logger

from src.gateway.base import PollingGateway


class SlackGateway(PollingGateway):
    API = "https://slack.com/api"

    def __init__(
        self,
        inbox,
        *,
        bot_token: str,
        app_token: str,
        allowed_channel_ids: set[str] | None = None,
    ) -> None:
        super().__init__(inbox, source="slack", allowed_chat_ids=allowed_channel_ids)
        self.bot_token = bot_token
        self.app_token = app_token
        self._bot_user_id: str | None = None

    def send_message(self, channel_id: str, text: str) -> bool:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{self.API}/chat.postMessage",
                    headers={"Authorization": f"Bearer {self.bot_token}"},
                    json={"channel": channel_id, "text": text[:4000]},
                )
                data = resp.json()
                if not data.get("ok"):
                    logger.warning("Slack 发送失败: {}", data.get("error"))
                    return False
                return True
        except Exception as exc:
            logger.warning("Slack 发送异常: {}", exc)
            return False

    def run_loop(self) -> None:
        asyncio.run(self._async_loop())

    async def _async_loop(self) -> None:
        import websockets

        while not self._stop.is_set():
            try:
                url = await self._open_connection()
                if not url:
                    await asyncio.sleep(10)
                    continue
                async with websockets.connect(url, ping_interval=30) as ws:
                    logger.info("Slack Socket Mode 已连接")
                    while not self._stop.is_set():
                        raw = await ws.recv()
                        await self._handle_socket_event(ws, raw)
            except Exception as exc:
                logger.warning("Slack 连接断开: {}", exc)
            if not self._stop.is_set():
                await asyncio.sleep(5)

    async def _open_connection(self) -> str | None:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{self.API}/apps.connections.open",
                headers={"Authorization": f"Bearer {self.app_token}"},
            )
            data = resp.json()
            if not data.get("ok"):
                logger.warning("Slack connections.open 失败: {}", data.get("error"))
                return None
            return str(data.get("url") or "")

    async def _handle_socket_event(self, ws, raw: str) -> None:
        envelope = json.loads(raw)
        if envelope.get("type") != "events_api":
            return
        ack = envelope.get("envelope_id")
        if ack:
            await ws.send(json.dumps({"envelope_id": ack}))
        payload = envelope.get("payload") or {}
        event = payload.get("event") or {}
        if event.get("type") != "message":
            return
        if event.get("subtype") or event.get("bot_id"):
            return
        channel = str(event.get("channel") or "")
        text = str(event.get("text") or "").strip()
        user = str(event.get("user") or "")
        if not channel or not text:
            return
        if not self._bot_user_id:
            self._bot_user_id = await self._fetch_bot_user()
        if self._bot_user_id and user == self._bot_user_id:
            return
        if channel.startswith("C") and self._bot_user_id:
            if f"<@{self._bot_user_id}>" not in text:
                return
            text = text.replace(f"<@{self._bot_user_id}>", "").strip()
        self.push_text(channel, text, meta={"user": user, "ts": event.get("ts")})

    async def _fetch_bot_user(self) -> str | None:
        with httpx.Client(timeout=20) as client:
            resp = client.post(
                f"{self.API}/auth.test",
                headers={"Authorization": f"Bearer {self.bot_token}"},
            )
            data = resp.json()
            if data.get("ok"):
                return str(data.get("user_id") or "")
        return None
