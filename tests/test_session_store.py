"""SessionStore 持久化测试。"""

from __future__ import annotations

from src.ui.session_store import SessionStore


def test_session_crud_and_events(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")

    sessions = store.list_sessions()
    assert len(sessions) == 1
    sid = sessions[0].id

    store.rename(sid, "工作会话")
    assert store.get(sid).title == "工作会话"

    store.append_event(sid, {"type": "user", "content": "hello"})
    store.append_event(sid, {"type": "assistant_end", "content": "hi"})

    events = store.load_events(sid)
    assert len(events) == 2
    assert events[0]["content"] == "hello"
    assert events[1]["content"] == "hi"

    new = store.create_session("临时")
    assert store.get(new.id) is not None

    store.clear_messages(sid)
    assert store.load_events(sid) == []

    store.close()


def test_reused_connection_across_operations(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    sid = store.list_sessions()[0].id

    store.append_event(sid, {"type": "meta", "content": "a"})
    conn_id = id(store._get_conn())
    store.append_event(sid, {"type": "meta", "content": "b"})
    assert id(store._get_conn()) == conn_id

    store.close()
    assert store._conn is None
