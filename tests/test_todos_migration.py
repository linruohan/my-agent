"""legacy todos.json 迁移测试。"""

from __future__ import annotations

import json
from pathlib import Path

from src.tools.task.store import TaskStore, migrate_legacy_todos_json


def test_migrate_legacy_todos_json(tmp_path: Path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    legacy = ws / "todos.json"
    legacy.write_text(
        json.dumps(
            [
                {
                    "id": 1,
                    "title": "旧待办",
                    "due_date": "2026-06-21",
                    "priority": "high",
                    "done": False,
                    "created_at": "2026-06-20T10:00:00",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    db = tmp_path / "task.db"
    store = TaskStore(db)

    import src.tools.task.store as store_mod

    orig = store_mod._LEGACY_TODOS
    store_mod._LEGACY_TODOS = legacy
    try:
        count = migrate_legacy_todos_json(store)
    finally:
        store_mod._LEGACY_TODOS = orig

    assert count == 1
    assert not legacy.exists()
    assert legacy.with_suffix(".json.migrated").exists()
    rows = store.list_all(include_done=True)
    assert len(rows) == 1
    assert rows[0].title == "旧待办"
    assert rows[0].status == "pending"
    assert "high" in rows[0].tags
