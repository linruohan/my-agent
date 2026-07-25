"""Gateway HTTP / Telegram / deliver_reply mock 测试。"""

from __future__ import annotations

import json
from http.client import HTTPConnection
from unittest.mock import MagicMock

from src.agent.hitl import (
    format_remote_approval_prompt,
    gateway_hitl_is_ask,
    parse_remote_approval_reply,
)
from src.gateway.http_server import GatewayHttpServer
from src.gateway.inbox import GatewayInbox
from src.gateway.service import GatewayService
from src.gateway.telegram_bot import TelegramGateway


def test_parse_remote_approval_reply():
    assert parse_remote_approval_reply("/approve") is True
    assert parse_remote_approval_reply("批准") is True
    assert parse_remote_approval_reply("/reject") is False
    assert parse_remote_approval_reply("拒绝") is False
    assert parse_remote_approval_reply("/approve 继续") is True
    assert parse_remote_approval_reply("随便问问") is None


def test_gateway_hitl_ask_policy():
    assert gateway_hitl_is_ask("ask") is True
    assert gateway_hitl_is_ask("interactive") is True
    assert gateway_hitl_is_ask("auto_reject") is False
    assert "批准" in format_remote_approval_prompt("危险操作")


def test_telegram_ingest_update_respects_allowlist(tmp_path):
    inbox = GatewayInbox(db_path=tmp_path / "gw.db")
    bot = TelegramGateway(inbox, bot_token="t", allowed_chat_ids={"100"})

    assert bot.ingest_update(
        {"update_id": 1, "message": {"chat": {"id": 999}, "text": "hi"}}
    ) is False
    assert inbox.pop_inbound() is None

    assert bot.ingest_update(
        {"update_id": 2, "message": {"chat": {"id": 100}, "text": "hello"}}
    ) is True
    msg = inbox.pop_inbound()
    assert msg is not None
    assert msg.source == "telegram"
    assert msg.chat_id == "100"
    assert msg.text == "hello"


def test_gateway_http_message_and_auth(tmp_path):
    inbox = GatewayInbox(db_path=tmp_path / "http.db")
    server = GatewayHttpServer(inbox, host="127.0.0.1", port=0, token="secret")
    # ThreadingHTTPServer 需要先 bind 才能拿到 port；此处用 start 后读 server
    server.start()
    assert server._server is not None
    port = server._server.server_address[1]
    try:
        conn = HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request(
            "POST",
            "/api/message",
            body=json.dumps({"text": "ping", "source": "http", "chat_id": "c1"}),
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        assert resp.status == 401
        conn.close()

        conn = HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request(
            "POST",
            "/api/message",
            body=json.dumps({"text": "ping", "source": "http", "chat_id": "c1"}),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer secret",
            },
        )
        resp = conn.getresponse()
        body = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 200
        assert body["ok"] is True
        conn.close()

        msg = inbox.pop_inbound()
        assert msg is not None
        assert msg.text == "ping"
    finally:
        server.stop()


def test_deliver_reply_fallback_to_outbound(tmp_path):
    inbox = GatewayInbox(db_path=tmp_path / "out.db")
    svc = GatewayService(inbox)
    # 无 bot 通道时写入 outbound
    svc.deliver_reply("telegram", "42", "hello world")
    batch = inbox.pop_outbound_batch(limit=5)
    assert len(batch) == 1
    assert batch[0].text == "hello world"
    assert batch[0].chat_id == "42"


def test_deliver_reply_uses_telegram_when_available(tmp_path):
    inbox = GatewayInbox(db_path=tmp_path / "out2.db")
    svc = GatewayService(inbox)
    mock_tg = MagicMock()
    mock_tg.send_message.return_value = True
    svc._telegram = mock_tg
    svc.deliver_reply("telegram", "7", "ok")
    mock_tg.send_message.assert_called_once_with("7", "ok")
    assert inbox.pop_outbound_batch() == []
