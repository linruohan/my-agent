"""Gateway 通道通用基类与鉴权辅助。"""

from __future__ import annotations

import threading
from typing import Callable

from loguru import logger

from src.gateway.inbox import GatewayInbox


class PollingGateway:
    """基于后台线程的轮询/长连接 Gateway 基类。"""

    def __init__(
        self,
        inbox: GatewayInbox,
        *,
        source: str,
        allowed_chat_ids: set[str] | None = None,
    ) -> None:
        self.inbox = inbox
        self.source = source
        self.allowed_chat_ids = allowed_chat_ids or set()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"gateway-{self.source}")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        try:
            self.run_loop()
        except Exception:
            logger.exception("Gateway {} 异常退出", self.source)

    def run_loop(self) -> None:
        raise NotImplementedError

    def _accept_chat(self, chat_id: str) -> bool:
        if not self.allowed_chat_ids:
            return True
        return chat_id in self.allowed_chat_ids

    def push_text(self, chat_id: str, text: str, *, meta: dict | None = None) -> None:
        if not chat_id or not text.strip():
            return
        if not self._accept_chat(chat_id):
            logger.debug("忽略未授权 {} chat_id={}", self.source, chat_id)
            return
        self.inbox.push_inbound(self.source, chat_id, text.strip(), meta=meta or {})
