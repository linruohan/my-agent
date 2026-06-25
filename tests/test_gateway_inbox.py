"""Gateway 收件箱状态机测试。"""

from __future__ import annotations

from src.gateway.inbox import GatewayInbox


def test_reclaim_stale_processing_on_startup(tmp_path):
    inbox = GatewayInbox(db_path=tmp_path / "gw.db")
    msg = inbox.push_inbound("http", "c1", "hello")
    inbox.pop_inbound()
    assert inbox.pop_inbound() is None

    reclaimed = inbox.reclaim_stale_processing()
    assert reclaimed == 1

    again = inbox.pop_inbound()
    assert again is not None
    assert again.id == msg.id


def test_mark_inbound_failed_and_done(tmp_path):
    inbox = GatewayInbox(db_path=tmp_path / "gw2.db")
    msg = inbox.push_inbound("telegram", "99", "ping")
    popped = inbox.pop_inbound()
    assert popped is not None

    inbox.mark_inbound_failed(popped.id)
    assert inbox.pop_inbound() is None

    msg2 = inbox.push_inbound("telegram", "99", "pong")
    popped2 = inbox.pop_inbound()
    assert popped2 is not None
    inbox.mark_inbound_done(popped2.id)
    assert inbox.pop_inbound() is None


def test_pop_outbound_batch_marks_sent(tmp_path):
    inbox = GatewayInbox(db_path=tmp_path / "gw3.db")
    mid = inbox.push_outbound("http", "c1", "reply")
    batch = inbox.pop_outbound_batch(limit=10)
    assert len(batch) == 1
    assert batch[0].id == mid
    assert inbox.pop_outbound_batch(limit=10) == []
