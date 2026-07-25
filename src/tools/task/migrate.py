"""旧版 todos.json → app.db 迁移。"""

from __future__ import annotations

import json

from loguru import logger

from src.infra.paths import DATA_DIR
from src.tools.task.store import TaskStore

_LEGACY_TODOS = DATA_DIR / "workspace" / "todos.json"


def migrate_legacy_todos_json(store: TaskStore | None = None) -> int:
    """将旧版 workspace/todos.json 一次性导入任务表，成功后重命名为 .migrated。"""
    if not _LEGACY_TODOS.is_file():
        return 0
    store = store or TaskStore()
    try:
        raw = json.loads(_LEGACY_TODOS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("读取 legacy todos.json 失败: {}", exc)
        return 0
    if not isinstance(raw, list):
        return 0

    imported = 0
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        priority = str(item.get("priority") or "normal")
        tags = [priority] if priority and priority != "normal" else []
        status = "done" if item.get("done") else "pending"
        due_date = item.get("due_date")
        due_at = f"{due_date}T00:00:00" if due_date else None
        created_at = item.get("created_at")
        if isinstance(created_at, str) and created_at and not created_at.endswith("Z"):
            if "+" not in created_at and "T" in created_at:
                created_at = f"{created_at}Z"
        try:
            store.add(
                title,
                "",
                due_at=due_at,
                tags=tags or None,
                status=status,
                created_at=str(created_at) if created_at else None,
            )
            imported += 1
        except ValueError:
            continue

    if imported >= 0:
        backup = _LEGACY_TODOS.with_suffix(".json.migrated")
        try:
            _LEGACY_TODOS.replace(backup)
            if imported:
                logger.info("已迁移 {} 条 legacy 待办至 task.db，备份为 {}", imported, backup.name)
        except OSError as exc:
            logger.warning("迁移完成但无法重命名 todos.json: {}", exc)
    return imported
