"""Gateway 会话映射、排队与 HITL 策略测试。"""

from __future__ import annotations

from src.agent.hitl import gateway_should_auto_approve
from src.gateway.inbox import GatewayInbox
from src.gateway.service import split_reply_text
from src.gateway.sessions import resolve_gateway_session
from src.ui.session_store import SessionStore


def test_resolve_gateway_session_creates_isolated_session(tmp_path):
    inbox = GatewayInbox(db_path=tmp_path / "gw.db")
    store = SessionStore(db_path=tmp_path / "sessions.db")

    sid1, tid1 = resolve_gateway_session(inbox, store, source="telegram", chat_id="100")
    sid2, tid2 = resolve_gateway_session(inbox, store, source="telegram", chat_id="200")
    sid1b, tid1b = resolve_gateway_session(inbox, store, source="telegram", chat_id="100")

    assert sid1 == sid1b
    assert tid1 == tid1b
    assert sid1 != sid2
    assert tid1 != tid2


def test_mark_inbound_pending_requeues_processing(tmp_path):
    inbox = GatewayInbox(db_path=tmp_path / "gw2.db")
    msg = inbox.push_inbound("http", "c1", "wait")
    popped = inbox.pop_inbound()
    assert popped is not None
    assert inbox.pop_inbound() is None

    inbox.mark_inbound_pending(popped.id)
    again = inbox.pop_inbound()
    assert again is not None
    assert again.id == msg.id


def test_count_pending_inbound(tmp_path):
    inbox = GatewayInbox(db_path=tmp_path / "gw3.db")
    assert inbox.count_pending_inbound() == 0
    inbox.push_inbound("http", "c1", "a")
    inbox.push_inbound("http", "c1", "b")
    assert inbox.count_pending_inbound() == 2


def test_gateway_should_auto_approve_policies():
    low = [{"name": "list_tasks", "args": {}}]
    medium = [{"name": "create_file", "args": {"path": "x", "content": "y"}}]
    high = [{"name": "write_local_file", "args": {"path": "x", "content": "y"}}]

    assert gateway_should_auto_approve(low, "approve_low") is True
    assert gateway_should_auto_approve(medium, "approve_low") is False
    assert gateway_should_auto_approve(medium, "approve_medium") is True
    assert gateway_should_auto_approve(high, "approve_medium") is False
    assert gateway_should_auto_approve(high, "auto_reject") is False


def test_split_reply_text_chunks_long_message():
    text = "a" * 5000
    chunks = split_reply_text(text, max_len=4000)
    assert len(chunks) == 2
    assert "".join(chunks) == text
