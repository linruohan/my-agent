"""统一数据库表结构初始化。"""

from __future__ import annotations

import sqlite3

from src.database.connection import ReusableSqliteStore
from src.database.schemas import ALL_SCHEMAS


def init_all_schemas_on_connection(conn: sqlite3.Connection) -> None:
    for script in ALL_SCHEMAS:
        conn.executescript(script)
    from src.tools.task.store import TaskStore

    TaskStore._migrate_columns(conn)


def init_all_schemas(store: ReusableSqliteStore) -> None:
    with store._connect() as conn:
        init_all_schemas_on_connection(conn)
