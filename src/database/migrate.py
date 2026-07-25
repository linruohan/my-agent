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

    # 目标已有数据时，跳过自增 id，避免主键冲突导致增量合并为 0
    insert_cols = cols
    if before > 0 and "id" in cols:
        insert_cols = [c for c in cols if c != "id"]
    if not insert_cols:
        return 0

    col_list = ", ".join(insert_cols)
    placeholders = ", ".join("?" for _ in insert_cols)
    select_list = ", ".join(cols)
    rows = source.execute(f"SELECT {select_list} FROM {table}").fetchall()
    if not rows:
        return 0

    payload: list[tuple] = []
    for row in rows:
        if insert_cols == cols:
            payload.append(tuple(row))
        else:
            payload.append(tuple(row[cols.index(c)] for c in insert_cols))

    # 目标非空时按非 id 列去重，避免重复导入
    if before > 0 and insert_cols != cols:
        existing = {
            tuple(r)
            for r in target.execute(f"SELECT {col_list} FROM {table}").fetchall()
        }
        payload = [row for row in payload if row not in existing]

    if not payload:
        return 0

    target.executemany(
        f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})",
        payload,
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


def list_legacy_database_files(data_dir: Path) -> list[str]:
    """返回 data_dir 下仍存在的旧版分散库文件名。"""
    return [name for name in LEGACY_DB_TABLES if (data_dir / name).is_file()]


def migrate_legacy_databases(target: Path, data_dir: Path) -> bool:
    """合并遗留分散库到 app.db（支持 app.db 已存在时的增量合并），成功后归档旧文件。"""
    legacy_files = list_legacy_database_files(data_dir)
    if not legacy_files:
        return False

    close_all_connections()

    mode = "增量合并" if target.is_file() else "首次合并"
    logger.info(
        "检测到 {} 个旧版数据库，正在{}至 {}",
        len(legacy_files),
        mode,
        target.name,
    )
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
        logger.info("旧库{}完成，写入 {} 条新记录", mode, copied_total)
    finally:
        target_conn.close()

    for legacy_name in legacy_files:
        try:
            _rename_legacy(data_dir / legacy_name)
        except OSError as exc:
            logger.warning("归档旧库 {} 失败: {}", legacy_name, exc)

    return True
