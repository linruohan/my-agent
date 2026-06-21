"""ReusableSqliteStore 与 timing 工具测试。"""

from __future__ import annotations

from src.infra.sqlite_store import ReusableSqliteStore
from src.tools.note.store import NoteStore
from src.tools.task.store import TaskStore


def test_reusable_sqlite_wal_and_reuse(tmp_path):
    store = ReusableSqliteStore(tmp_path / "t.db")
    with store._connect() as conn:
        conn.execute("CREATE TABLE kv (k TEXT PRIMARY KEY, v TEXT)")
        conn.execute("INSERT INTO kv VALUES ('a', '1')")
    first = id(store._get_conn())
    with store._connect() as conn:
        row = conn.execute("SELECT v FROM kv WHERE k='a'").fetchone()
        assert row["v"] == "1"
    assert id(store._get_conn()) == first
    store.close()
    assert store._conn is None


def test_note_store_reuses_connection(tmp_path):
    store = NoteStore(tmp_path / "note.db")
    store.add("t", "body")
    conn_id = id(store._get_conn())
    assert len(store.list_all()) == 1
    assert id(store._get_conn()) == conn_id
    store.close()


def test_task_store_reuses_connection(tmp_path):
    store = TaskStore(tmp_path / "task.db")
    row = store.add(title="x", content="y")
    assert row.id >= 1
    conn_id = id(store._get_conn())
    assert store.get(row.id) is not None
    assert id(store._get_conn()) == conn_id
    store.close()
