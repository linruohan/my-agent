"""将旧版分散 .db 文件合并至统一 app.db。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from src.database.connection import _open_sqlite, close_all_connections
from src.database.paths import LEGACY_DB_TABLES


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _copy_table(target: sqlite3.Connection, source: sqlite3.Connection, table: str) -> int:
    if not _table_exists(source, table) or not _table_exists(target, table):
        return 0
    before = target.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    cols = [row[1] for row in source.execute(f"PRAGMA table_info({table})")]
    if not cols:
        return 0
    col_list = ", ".join(cols)
    placeholders = ", ".join("?" for _ in cols)
    rows = source.execute(f"SELECT {col_list} FROM {table}").fetchall()
    if not rows:
        return 0
    target.executemany(
        f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})",
        rows,
    )
    after = target.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return int(after) - int(before)


def _open_legacy_readonly(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _rename_legacy(path: Path) -> None:
    backup = path.with_suffix(path.suffix + ".migrated")
    if backup.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup = path.with_suffix(f"{path.suffix}.{stamp}.migrated")
    path.rename(backup)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(path) + suffix)
        if sidecar.is_file():
            sidecar.rename(Path(str(backup) + suffix))


def migrate_legacy_databases(target: Path, data_dir: Path) -> bool:
    """若存在旧库且 target 尚未创建，则合并数据并归档旧文件。返回是否执行了迁移。"""
    if target.is_file():
        return False

    legacy_files = [name for name in LEGACY_DB_TABLES if (data_dir / name).is_file()]
    if not legacy_files:
        return False

    close_all_connections()

    logger.info("检测到 {} 个旧版数据库，正在合并至 {}", len(legacy_files), target.name)
    target_conn = _open_sqlite(target)
    try:
        from src.database.schema import init_all_schemas_on_connection

        init_all_schemas_on_connection(target_conn)
        target_conn.commit()

        copied_total = 0
        for legacy_name in legacy_files:
            legacy_path = (data_dir / legacy_name).resolve()
            source_conn = _open_legacy_readonly(legacy_path)
            try:
                for table in LEGACY_DB_TABLES[legacy_name]:
                    try:
                        copied_total += _copy_table(target_conn, source_conn, table)
                    except sqlite3.Error as exc:
                        logger.warning("迁移表 {} 自 {} 失败: {}", table, legacy_name, exc)
                target_conn.commit()
            finally:
                source_conn.close()

        target_conn.execute(
            "INSERT OR REPLACE INTO db_meta (key, value) VALUES (?, ?)",
            ("migrated_from_legacy", datetime.now(timezone.utc).isoformat()),
        )
        target_conn.commit()
        logger.info("旧库合并完成，写入 {} 条新记录", copied_total)
    finally:
        target_conn.close()

    for legacy_name in legacy_files:
        try:
            _rename_legacy(data_dir / legacy_name)
        except OSError as exc:
            logger.warning("归档旧库 {} 失败: {}", legacy_name, exc)

    return True
