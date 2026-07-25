"""Gateway 统一调度：HTTP + Telegram + Discord + Slack。"""

from __future__ import annotations

import threading
from typing import Callable

import httpx
from loguru import logger

from src.gateway.config import load_gateway_config, validate_http_token
from src.gateway.discord_bot import DiscordGateway
from src.gateway.http_server import GatewayHttpServer
from src.gateway.inbox import GatewayInbox, GatewayMessage
from src.gateway.slack_bot import SlackGateway
from src.gateway.telegram_bot import TelegramGateway

_MAX_REPLY_CHARS = 4000


def post_http_webhook(
    url: str,
    *,
    source: str,
    chat_id: str,
    text: str,
    token: str = "",
    timeout: float = 15.0,
) -> bool:
    """向配置的 webhook URL 推送一条出站消息。"""
    if not (url or "").strip():
        return False
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                url.strip(),
                json={"source": source, "chat_id": chat_id, "text": text},
                headers=headers,
            )
            if 200 <= resp.status_code < 300:
                return True
            logger.warning("HTTP webhook 失败 status={} body={}", resp.status_code, resp.text[:200])
            return False
    except Exception as exc:
        logger.warning("HTTP webhook 异常: {}", exc)
        return False


def split_reply_text(text: str, *, max_len: int = _MAX_REPLY_CHARS) -> list[str]:
    body = (text or "").strip()
    if not body:
        return []
    if len(body) <= max_len:
        return [body]
    chunks: list[str] = []
    while body:
        if len(body) <= max_len:
            chunks.append(body)
            break
        split_at = body.rfind("\n", 0, max_len)
        if split_at < max_len // 2:
            split_at = max_len
        chunks.append(body[:split_at].rstrip())
        body = body[split_at:].lstrip()
    return chunks


class GatewayService:
    """消息网关：外部通道 ↔ Agent 收件箱。"""

    def __init__(
        self,
        inbox: GatewayInbox | None = None,
        *,
        on_inbound: Callable[[GatewayMessage], None] | None = None,
        can_dispatch: Callable[[], bool] | None = None,
    ) -> None:
        self.inbox = inbox or GatewayInbox()
        self._on_inbound = on_inbound
        self._can_dispatch = can_dispatch
        self._http: GatewayHttpServer | None = None
        self._telegram: TelegramGateway | None = None
        self._discord: DiscordGateway | None = None
        self._slack: SlackGateway | None = None
        self._http_webhook_url: str = ""
        self._http_token: str = ""
        self._stop = threading.Event()
        self._dispatch_thread: threading.Thread | None = None

    def start(self) -> None:
        cfg = load_gateway_config()
        if not cfg.get("enabled"):
            logger.debug("Gateway 未启用")
            return

        self._http_webhook_url = str(cfg.get("http_webhook_url") or "").strip()
        self._http_token = str(cfg.get("http_token") or "").strip()

        if cfg.get("http_enabled"):
            token_error = validate_http_token(cfg)
            if token_error:
                logger.error("{}", token_error)
            else:
                self._http = GatewayHttpServer(
                    self.inbox,
                    host=cfg["http_host"],
                    port=cfg["http_port"],
                    token=cfg["http_token"],
                )
                self._http.start()

        tg = cfg.get("telegram") or {}
        if tg.get("enabled") and tg.get("bot_token"):
            self._telegram = TelegramGateway(
                self.inbox,
                bot_token=tg["bot_token"],
                allowed_chat_ids=set(tg.get("allowed_chat_ids") or []),
                poll_interval=float(tg.get("poll_interval") or 2.0),
            )
            self._telegram.start()

        dc = cfg.get("discord") or {}
        if dc.get("enabled") and dc.get("bot_token"):
            self._discord = DiscordGateway(
                self.inbox,
                bot_token=dc["bot_token"],
                allowed_channel_ids=set(dc.get("allowed_channel_ids") or []),
            )
            self._discord.start()

        sk = cfg.get("slack") or {}
        if sk.get("enabled") and sk.get("bot_token") and sk.get("app_token"):
            self._slack = SlackGateway(
                self.inbox,
                bot_token=sk["bot_token"],
                app_token=sk["app_token"],
                allowed_channel_ids=set(sk.get("allowed_channel_ids") or []),
            )
            self._slack.start()

        if self._on_inbound and not (self._dispatch_thread and self._dispatch_thread.is_alive()):
            self._stop.clear()
            self._dispatch_thread = threading.Thread(
                target=self._dispatch_loop,
                daemon=True,
                name="gateway-dispatch",
            )
            self._dispatch_thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._http:
            self._http.stop()
        if self._telegram:
            self._telegram.stop()
        if self._discord:
            self._discord.stop()
        if self._slack:
            self._slack.stop()

    def deliver_reply(self, source: str, chat_id: str, text: str) -> None:
        chunks = split_reply_text(text)
        if not chunks:
            return
        for chunk in chunks:
            if not self._deliver_reply_chunk(source, chat_id, chunk):
                self.inbox.push_outbound(source, chat_id, chunk)

    def _deliver_reply_chunk(self, source: str, chat_id: str, body: str) -> bool:
        if source == "telegram" and self._telegram:
            if self._telegram.send_message(chat_id, body):
                return True
        if source == "discord" and self._discord:
            if self._discord.send_message(chat_id, body):
                return True
        if source == "slack" and self._slack:
            if self._slack.send_message(chat_id, body):
                return True
        # 非即时通道（含 http）：优先 webhook 推送，失败由调用方入 outbound 队列
        if self._http_webhook_url and source not in ("telegram", "discord", "slack"):
            if post_http_webhook(
                self._http_webhook_url,
                source=source or "http",
                chat_id=chat_id,
                text=body,
                token=self._http_token,
            ):
                return True
        return False

    def _dispatch_loop(self) -> None:
        while not self._stop.is_set():
            if self._can_dispatch and not self._can_dispatch():
                self._stop.wait(1.0)
                continue
            msg = self.inbox.pop_inbound()
            if msg and self._on_inbound:
                try:
                    self._on_inbound(msg)
                except Exception:
                    logger.exception("Gateway 入站分发失败")
                    self.inbox.mark_inbound_failed(msg.id)
            self._stop.wait(0.5 if msg else 1.0)

    def reload(self, on_inbound: Callable[[GatewayMessage], None] | None = None) -> None:
        self.stop()
        if on_inbound:
            self._on_inbound = on_inbound
        self.start()

    def status(self) -> dict:
        cfg = load_gateway_config()
        return {
            "enabled": cfg.get("enabled"),
            "http": f"http://{cfg['http_host']}:{cfg['http_port']}/" if cfg.get("http_enabled") else "",
            "telegram": bool((cfg.get("telegram") or {}).get("enabled")),
            "discord": bool((cfg.get("discord") or {}).get("enabled")),
            "slack": bool((cfg.get("slack") or {}).get("enabled")),
            "remote_hitl": cfg.get("remote_hitl"),
            "http_webhook": bool(cfg.get("http_webhook_url")),
            "pending_inbound": self.inbox.count_pending_inbound(),
        }
