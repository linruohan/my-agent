"""应用数据库生命周期管理。"""

from __future__ import annotations

from pathlib import Path

from src.database.connection import ReusableSqliteStore, close_all_connections
from src.database.migrate import migrate_legacy_databases
from src.database.paths import app_db_path
from src.database.schema import init_all_schemas

_initialized = False
_init_lock = __import__("threading").Lock()


def ensure_database(data_dir: Path | None = None) -> Path:
    """确保 app.db 存在、结构完整，并在需要时从旧库迁移。"""
    global _initialized
    if data_dir is None:
        from src.infra.paths import DATA_DIR

        root = DATA_DIR
    else:
        root = data_dir
    root.mkdir(parents=True, exist_ok=True)
    db = app_db_path(root)

    with _init_lock:
        migrated = migrate_legacy_databases(db, root)
        if not db.is_file() or migrated:
            store = ReusableSqliteStore(db, foreign_keys=True)
            init_all_schemas(store)
            store.close()
        _initialized = True
    return db


def close_database() -> None:
    """关闭所有共享 SQLite 连接。"""
    global _initialized
    close_all_connections()
    _initialized = False
