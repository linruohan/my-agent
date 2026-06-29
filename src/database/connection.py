"""SQLite 共享连接池与可复用 Store 基类。"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass
class _PoolEntry:
    conn: sqlite3.Connection
    lock: threading.Lock
    refs: int = 0


_POOL: dict[str, _PoolEntry] = {}
_POOL_GUARD = threading.Lock()


def _open_sqlite(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def _pool_key(db_path: Path) -> str:
    return str(db_path.resolve())


def acquire_connection(db_path: Path) -> tuple[sqlite3.Connection, threading.Lock, bool]:
    """获取（或创建）共享连接，返回 (conn, lock, pooled)。"""
    key = _pool_key(db_path)
    with _POOL_GUARD:
        entry = _POOL.get(key)
        if entry is None:
            entry = _PoolEntry(conn=_open_sqlite(db_path), lock=threading.Lock(), refs=0)
            _POOL[key] = entry
        entry.refs += 1
        return entry.conn, entry.lock, True


def release_connection(db_path: Path) -> None:
    key = _pool_key(db_path)
    with _POOL_GUARD:
        entry = _POOL.get(key)
        if entry is None:
            return
        entry.refs -= 1
        if entry.refs <= 0:
            entry.conn.close()
            del _POOL[key]


def close_all_connections() -> None:
    with _POOL_GUARD:
        for entry in _POOL.values():
            entry.conn.close()
        _POOL.clear()


class ReusableSqliteStore:
    """按 db 路径复用单连接，避免同库多实例重复 open。"""

    def __init__(self, db_path: Path, *, foreign_keys: bool = False, shared: bool = True) -> None:
        self.db_path = Path(db_path)
        self._foreign_keys = foreign_keys  # 保留参数兼容；统一库始终开启外键
        self._shared = shared
        self._lock: threading.Lock | None = None
        self._conn: sqlite3.Connection | None = None
        self._pooled = False

    def _get_conn(self) -> sqlite3.Connection:
        if self._shared:
            if self._conn is None:
                conn, lock, pooled = acquire_connection(self.db_path)
                self._conn = conn
                self._lock = lock
                self._pooled = pooled
            return self._conn
        if self._conn is None:
            self._conn = _open_sqlite(self.db_path)
            self._lock = threading.Lock()
        return self._conn

    def close(self) -> None:
        if self._pooled:
            release_connection(self.db_path)
            self._conn = None
            self._lock = None
            self._pooled = False
            return
        if self._conn is not None:
            with self._lock or threading.Lock():
                self._conn.close()
            self._conn = None
            self._lock = None

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = self._get_conn()
        lock = self._lock or threading.Lock()
        with lock:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
