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


def test_load_events_limit_keeps_recent(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    sid = store.list_sessions()[0].id
    for i in range(5):
        store.append_event(sid, {"type": "user", "content": f"m{i}"})
    assert store.count_events(sid) == 5
    recent = store.load_events(sid, limit=2)
    assert len(recent) == 2
    assert recent[0]["content"] == "m3"
    assert recent[1]["content"] == "m4"
    store.close()


def test_append_event_uses_monotonic_next_seq(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    sid = store.list_sessions()[0].id
    store.append_event(sid, {"type": "user", "content": "a"})
    store.append_event(sid, {"type": "user", "content": "b"})
    with store._connect() as conn:
        seqs = [
            int(r["seq"])
            for r in conn.execute(
                "SELECT seq FROM session_messages WHERE session_id = ? ORDER BY seq",
                (sid,),
            )
        ]
        next_seq = int(
            conn.execute("SELECT next_seq FROM sessions WHERE id = ?", (sid,)).fetchone()[
                "next_seq"
            ]
        )
    assert seqs == [1, 2]
    assert next_seq == 2
    store.clear_messages(sid)
    with store._connect() as conn:
        assert (
            int(
                conn.execute("SELECT next_seq FROM sessions WHERE id = ?", (sid,)).fetchone()[
                    "next_seq"
                ]
            )
            == 0
        )
    store.close()


def test_migrate_legacy_sessions_without_next_seq(tmp_path):
    import sqlite3

    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE session_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            seq INTEGER NOT NULL,
            event_json TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO sessions VALUES ('s1', 't1', '旧', '2020-01-01', '2020-01-01')"
    )
    conn.execute(
        "INSERT INTO session_messages (session_id, seq, event_json) VALUES ('s1', 3, '{}')"
    )
    conn.commit()
    conn.close()

    store = SessionStore(db)
    store.append_event("s1", {"type": "user", "content": "new"})
    with store._connect() as conn:
        next_seq = int(
            conn.execute("SELECT next_seq FROM sessions WHERE id = ?", ("s1",)).fetchone()[
                "next_seq"
            ]
        )
        max_seq = int(
            conn.execute(
                "SELECT MAX(seq) AS m FROM session_messages WHERE session_id = ?",
                ("s1",),
            ).fetchone()["m"]
        )
    assert next_seq == 4
    assert max_seq == 4
    store.close()
