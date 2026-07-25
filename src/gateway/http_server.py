"""Gateway 本地 HTTP API（Webhook / 长轮询）。"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import parse_qs, urlparse

from loguru import logger

from src.gateway.inbox import GatewayInbox


class GatewayHttpServer:
    def __init__(
        self,
        inbox: GatewayInbox,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        token: str = "",
    ) -> None:
        self.inbox = inbox
        self.host = host
        self.port = port
        self.token = token
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        inbox = self.inbox
        token = self.token

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:  # noqa: A003
                logger.debug("[gateway-http] " + format, *args)

            def _auth_ok(self) -> bool:
                # 空 token 一律拒绝（GatewayService 在启用 HTTP 前已校验）
                if not token:
                    return False
                auth = self.headers.get("Authorization", "")
                if auth == f"Bearer {token}":
                    return True
                qs = parse_qs(urlparse(self.path).query)
                return qs.get("token", [""])[0] == token

            def _json(self, code: int, payload: dict) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _read_json(self) -> dict:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    data = json.loads(raw.decode("utf-8"))
                    return data if isinstance(data, dict) else {}
                except json.JSONDecodeError:
                    return {}

            def do_GET(self) -> None:  # noqa: N802
                if not self._auth_ok():
                    self._json(401, {"ok": False, "error": "unauthorized"})
                    return
                path = urlparse(self.path).path
                if path == "/health":
                    self._json(200, {"ok": True, "service": "my-agent-gateway"})
                    return
                if path == "/api/outbound":
                    msgs = inbox.pop_outbound_batch(limit=20)
                    self._json(
                        200,
                        {
                            "ok": True,
                            "messages": [
                                {
                                    "id": m.id,
                                    "source": m.source,
                                    "chat_id": m.chat_id,
                                    "text": m.text,
                                }
                                for m in msgs
                            ],
                        },
                    )
                    return
                self._json(404, {"ok": False, "error": "not found"})

            def do_POST(self) -> None:  # noqa: N802
                if not self._auth_ok():
                    self._json(401, {"ok": False, "error": "unauthorized"})
                    return
                path = urlparse(self.path).path
                if path != "/api/message":
                    self._json(404, {"ok": False, "error": "not found"})
                    return
                data = self._read_json()
                text = str(data.get("text") or "").strip()
                if not text:
                    self._json(400, {"ok": False, "error": "text required"})
                    return
                source = str(data.get("source") or "http")
                chat_id = str(data.get("chat_id") or "default")
                msg = inbox.push_inbound(source, chat_id, text, meta=data.get("meta") or {})
                self._json(200, {"ok": True, "id": msg.id})

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="gateway-http",
        )
        self._thread.start()
        logger.info("Gateway HTTP 已启动 http://{}:{}/", self.host, self.port)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None
