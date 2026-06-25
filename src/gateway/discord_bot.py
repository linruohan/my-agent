"""Discord Bot Gateway（WebSocket）。"""

from __future__ import annotations

import asyncio
import json

import httpx
from loguru import logger

from src.gateway.base import PollingGateway

# GUILDS | GUILD_MESSAGES | DIRECT_MESSAGES | MESSAGE_CONTENT
_DISCORD_INTENTS = (1 << 0) | (1 << 9) | (1 << 12) | (1 << 15)


class DiscordGateway(PollingGateway):
    GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"
    API = "https://discord.com/api/v10"

    def __init__(
        self,
        inbox,
        *,
        bot_token: str,
        allowed_channel_ids: set[str] | None = None,
    ) -> None:
        super().__init__(inbox, source="discord", allowed_chat_ids=allowed_channel_ids)
        self.bot_token = bot_token
        self._bot_user_id: str | None = None

    def send_message(self, channel_id: str, text: str) -> bool:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{self.API}/channels/{channel_id}/messages",
                    headers={"Authorization": f"Bot {self.bot_token}"},
                    json={"content": text[:2000]},
                )
                resp.raise_for_status()
                return True
        except Exception as exc:
            logger.warning("Discord 发送失败: {}", exc)
            return False

    def run_loop(self) -> None:
        asyncio.run(self._async_loop())

    async def _async_loop(self) -> None:
        import websockets

        while not self._stop.is_set():
            try:
                async with websockets.connect(self.GATEWAY_URL, ping_interval=None) as ws:
                    await self._session(ws)
            except Exception as exc:
                logger.warning("Discord 连接断开: {}", exc)
            if not self._stop.is_set():
                await asyncio.sleep(5)

    async def _session(self, ws) -> None:
        heartbeat_interval: float | None = None
        seq: int | None = None

        async def heartbeat() -> None:
            while not self._stop.is_set():
                await asyncio.sleep(heartbeat_interval or 30)
                await ws.send(json.dumps({"op": 1, "d": seq}))

        hb_task: asyncio.Task | None = None
        while not self._stop.is_set():
            raw = await ws.recv()
            payload = json.loads(raw)
            op = payload.get("op")
            t = payload.get("t")
            d = payload.get("d") or {}
            if payload.get("s") is not None:
                seq = payload["s"]

            if op == 10:
                heartbeat_interval = d.get("heartbeat_interval", 45000) / 1000.0
                await ws.send(
                    json.dumps(
                        {
                            "op": 2,
                            "d": {
                                "token": f"Bot {self.bot_token}",
                                "intents": _DISCORD_INTENTS,
                                "properties": {
                                    "$os": "windows",
                                    "$browser": "my-agent",
                                    "$device": "my-agent",
                                },
                            },
                        }
                    )
                )
                if hb_task is None:
                    hb_task = asyncio.create_task(heartbeat())
            elif op == 0 and t == "READY":
                user = d.get("user") or {}
                self._bot_user_id = str(user.get("id") or "")
                logger.info("Discord Gateway READY bot={}", user.get("username"))
            elif op == 0 and t == "MESSAGE_CREATE":
                self._on_message(d)

    def _on_message(self, data: dict) -> None:
        author = data.get("author") or {}
        if author.get("bot"):
            return
        channel_id = str(data.get("channel_id") or "")
        raw_content = str(data.get("content") or "").strip()
        if not channel_id or not raw_content:
            return
        guild_id = data.get("guild_id")
        if guild_id:
            if not self._bot_user_id or f"<@{self._bot_user_id}>" not in raw_content:
                return
            content = raw_content.replace(f"<@{self._bot_user_id}>", "").strip()
        else:
            content = raw_content
        if not content:
            return
        self.push_text(channel_id, content, meta={"message_id": data.get("id")})
