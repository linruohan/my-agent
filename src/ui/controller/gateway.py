"""Gateway 入站消息与 Agent 回复投递。"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.gateway.inbox import GatewayMessage
from src.gateway.sessions import resolve_gateway_session


class GatewayMixin:
    """外部消息通道（HTTP / Telegram）与 Agent 桥接。"""

    def _init_gateway(self) -> None:
        self._gateway_context: dict[str, Any] | None = None
        from src.gateway import GatewayInbox, GatewayService

        self._gateway_inbox = GatewayInbox()
        reclaimed = self._gateway_inbox.reclaim_stale_processing()
        if reclaimed:
            logger.warning("[gateway] 回收 {} 条卡住的 processing 入站消息", reclaimed)
        self._gateway = GatewayService(
            self._gateway_inbox,
            on_inbound=self._handle_gateway_inbound,
            can_dispatch=lambda: not self._is_busy(),
        )
        self._gateway.start()

    def _resolve_gateway_session(self, source: str, chat_id: str) -> tuple[str, str]:
        return resolve_gateway_session(
            self._gateway_inbox,
            self._session_store,
            source=source,
            chat_id=chat_id,
        )

    def _handle_gateway_inbound(self, msg: GatewayMessage) -> None:
        if self._is_busy():
            self._gateway_inbox.mark_inbound_pending(msg.id)
            logger.debug("[gateway] Agent 忙，消息 {} 重新排队", msg.id[:8])
            return

        session_id, thread_id = self._resolve_gateway_session(msg.source, msg.chat_id)
        prefix = f"[{msg.source}] "
        display = f"{prefix}{msg.text}"
        self._gateway_context = {
            "id": msg.id,
            "source": msg.source,
            "chat_id": msg.chat_id,
            "session_id": session_id,
            "thread_id": thread_id,
        }
        logger.info(
            "[gateway] 入站 {} chat={} session={} len={}",
            msg.source,
            msg.chat_id,
            session_id[:8],
            len(msg.text),
        )
        ok = self.send_message(
            {"text": msg.text, "attachments": []},
            gateway_label=display,
        )
        if not ok:
            self._gateway_inbox.mark_inbound_pending(msg.id)
            self._gateway_context = None

    def _gateway_deliver_reply(self, response: str) -> None:
        ctx = self._gateway_context
        if not ctx:
            return
        self._gateway.deliver_reply(ctx["source"], ctx["chat_id"], response)
        self._gateway_inbox.mark_inbound_done(ctx["id"])
        self._gateway_context = None

    def _gateway_fail(self, reason: str = "") -> None:
        """入站处理失败：标记 failed 并向远程通道回复（如有说明）。"""
        ctx = self._gateway_context
        if not ctx:
            return
        self._gateway_inbox.mark_inbound_failed(ctx["id"])
        if reason.strip():
            self._gateway.deliver_reply(ctx["source"], ctx["chat_id"], reason.strip())
        self._gateway_context = None

    def _gateway_compose_aborted(self) -> None:
        """Compose 线程结束但未进入 Agent 运行时的兜底。"""
        if self._gateway_context and not self._running and not self._awaiting_approval:
            self._gateway_fail("消息处理未完成，请重试。")

    def _persist_session_id(self) -> str:
        if self._gateway_context:
            return str(self._gateway_context.get("session_id") or self._session_id)
        return self._session_id

    def gateway_status(self) -> dict[str, Any]:
        return self._gateway.status()
