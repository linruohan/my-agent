"""统一数据库模块测试。"""

from __future__ import annotations

import sqlite3

from src.database import app_db_path, close_database, ensure_database
from src.database.migrate import migrate_legacy_databases
from src.tools.note.store import NoteStore
from src.tools.task.store import TaskStore
from src.ui.session_store import SessionStore


def test_ensure_database_creates_unified_schema(tmp_path):
    data = tmp_path / "data"
    db = ensure_database(data)
    assert db == data / "app.db"
    assert db.is_file()

    conn = sqlite3.connect(db)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    conn.close()
    assert "sessions" in tables
    assert "tasks" in tables
    assert "notes" in tables
    assert "search_cache" in tables
    assert "timing_events" in tables
    assert "gateway_inbound" in tables
    assert "cron_jobs" in tables
    assert "conversation_vectors" in tables
    assert "learning_records" in tables
    close_database()


def test_stores_share_connection_on_same_db(tmp_path):
    db = tmp_path / "app.db"
    session = SessionStore(db)
    task = TaskStore(db)
    note = NoteStore(db)
    assert id(session._get_conn()) == id(task._get_conn()) == id(note._get_conn())
    task.add(title="t", content="c")
    note.add("n", "body")
    session.close()
    task.close()
    note.close()
    close_database()


def test_migrate_legacy_databases(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    legacy = data / "note.db"
    note = NoteStore(legacy)
    note.add("旧笔记", "内容")
    note.close()
    close_database()

    target = app_db_path(data)
    assert migrate_legacy_databases(target, data) is True
    assert target.is_file()
    assert not legacy.is_file()
    assert legacy.with_suffix(".db.migrated").is_file()

    migrated = NoteStore(target)
    rows = migrated.list_all()
    migrated.close()
    close_database()
    assert len(rows) == 1
    assert rows[0].title == "旧笔记"


def test_migrate_legacy_databases_incremental(tmp_path):
    """app.db 已存在时仍可增量合并遗留库。"""
    data = tmp_path / "data"
    data.mkdir()
    target = app_db_path(data)
    ensure_database(data)

    existing = NoteStore(target)
    existing.add("已有笔记", "keep")
    existing.close()
    close_database()

    legacy = data / "note.db"
    note = NoteStore(legacy)
    note.add("增量笔记", "new")
    note.close()
    close_database()

    assert migrate_legacy_databases(target, data) is True
    assert not legacy.is_file()
    assert legacy.with_suffix(".db.migrated").is_file()

    store = NoteStore(target)
    titles = {r.title for r in store.list_all()}
    store.close()
    close_database()
    assert "已有笔记" in titles
    assert "增量笔记" in titles
