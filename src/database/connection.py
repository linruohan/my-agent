"""SQLite 共享连接池与可复用 Store 基类。"""

from __future__ import annotations

import atexit
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from loguru import logger


@dataclass
class _PoolEntry:
    conn: sqlite3.Connection
    lock: threading.Lock
    refs: int = 0
    idle_since: float | None = None


_POOL: dict[str, _PoolEntry] = {}
_POOL_GUARD = threading.Lock()
_MAX_IDLE_CONNECTIONS = 5


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


def _evict_idle_locked() -> None:
    """在已持有 _POOL_GUARD 时淘汰多余空闲连接。"""
    idle = [(key, entry) for key, entry in _POOL.items() if entry.refs <= 0]
    overflow = len(idle) - _MAX_IDLE_CONNECTIONS
    if overflow <= 0:
        return
    idle.sort(key=lambda item: item[1].idle_since or 0.0)
    for key, entry in idle[:overflow]:
        try:
            entry.conn.close()
            logger.debug("[db-pool] 淘汰空闲连接: {}", key)
        except Exception as exc:
            logger.debug("[db-pool] 淘汰空闲连接失败: {} - {}", key, exc)
        _POOL.pop(key, None)


def acquire_connection(db_path: Path) -> tuple[sqlite3.Connection, threading.Lock, bool]:
    """获取（或创建）共享连接，返回 (conn, lock, pooled)。"""
    key = _pool_key(db_path)
    with _POOL_GUARD:
        entry = _POOL.get(key)
        if entry is None:
            entry = _PoolEntry(conn=_open_sqlite(db_path), lock=threading.Lock(), refs=0)
            _POOL[key] = entry
            logger.debug("[db-pool] 创建新连接: {}", key)
        entry.refs += 1
        entry.idle_since = None
        return entry.conn, entry.lock, True


def release_connection(db_path: Path) -> None:
    key = _pool_key(db_path)
    with _POOL_GUARD:
        entry = _POOL.get(key)
        if entry is None:
            logger.warning("[db-pool] 释放不存在的连接: {}", key)
            return
        entry.refs -= 1
        if entry.refs <= 0:
            entry.refs = 0
            entry.idle_since = time.monotonic()
            _evict_idle_locked()


@contextmanager
def connection_scope(db_path: Path) -> Iterator[tuple[sqlite3.Connection, threading.Lock]]:
    """上下文管理器：自动获取和释放连接，防止泄漏。"""
    conn, lock, pooled = acquire_connection(db_path)
    try:
        yield conn, lock
    finally:
        if pooled:
            release_connection(db_path)


def close_all_connections() -> None:
    with _POOL_GUARD:
        stale = list(_POOL.keys())
        if stale:
            logger.debug("[db-pool] 关闭 {} 个连接", len(stale))
            for key in stale:
                entry = _POOL[key]
                try:
                    entry.conn.close()
                except Exception as exc:
                    logger.debug("[db-pool] 关闭连接异常: {} - {}", key, exc)
        _POOL.clear()


def _check_leaked_connections() -> None:
    with _POOL_GUARD:
        active = [key for key, entry in _POOL.items() if entry.refs > 0]
        if active:
            logger.warning(
                "[db-pool] 程序退出时仍有 {} 个连接未释放: {}",
                len(active),
                active,
            )


atexit.register(_check_leaked_connections)
atexit.register(close_all_connections)


class ReusableSqliteStore:
    """按 db 路径复用长连接；Store 存活期间保持引用，避免热路径反复建连。"""

    def __init__(self, db_path: Path, *, foreign_keys: bool = False, shared: bool = True) -> None:
        self.db_path = Path(db_path)
        self._foreign_keys = foreign_keys
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
