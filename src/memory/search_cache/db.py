"""搜索缓存 SQLite 存储。"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

from src.infra.sqlite_store import ReusableSqliteStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_cache (
    cache_key    TEXT PRIMARY KEY,
    search_query TEXT NOT NULL,
    response     TEXT NOT NULL,
    search_ok    INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    hit_count    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS search_cache_user_queries (
    cache_key  TEXT NOT NULL,
    user_query TEXT NOT NULL,
    added_at   TEXT NOT NULL,
    PRIMARY KEY (cache_key, user_query),
    FOREIGN KEY (cache_key) REFERENCES search_cache(cache_key) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_search_cache_expires ON search_cache(expires_at);
"""


@dataclass
class CacheRow:
    cache_key: str
    search_query: str
    response: str
    user_queries: list[str] = field(default_factory=list)
    search_ok: bool = True
    created_at: str = ""
    expires_at: str = ""
    hit_count: int = 0


class SearchCacheStore(ReusableSqliteStore):
    def __init__(self, db_path: Path) -> None:
        super().__init__(db_path, foreign_keys=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM search_cache WHERE expires_at > ?",
                (self._now_iso(),),
            ).fetchone()
            return int(row["c"]) if row else 0

    def list_active(self) -> list[CacheRow]:
        now = self._now_iso()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT cache_key, search_query, response, search_ok,
                       created_at, expires_at, hit_count
                FROM search_cache
                WHERE expires_at > ?
                ORDER BY created_at DESC
                """,
                (now,),
            ).fetchall()
            result: list[CacheRow] = []
            for row in rows:
                uq_rows = conn.execute(
                    "SELECT user_query FROM search_cache_user_queries WHERE cache_key = ?",
                    (row["cache_key"],),
                ).fetchall()
                result.append(
                    CacheRow(
                        cache_key=row["cache_key"],
                        search_query=row["search_query"],
                        response=row["response"],
                        user_queries=[r["user_query"] for r in uq_rows],
                        search_ok=bool(row["search_ok"]),
                        created_at=row["created_at"],
                        expires_at=row["expires_at"],
                        hit_count=int(row["hit_count"]),
                    )
                )
            return result

    def upsert(
        self,
        *,
        cache_key: str,
        search_query: str,
        response: str,
        user_query: str,
        search_ok: bool,
        ttl_days: int,
        max_user_queries: int,
    ) -> None:
        now = datetime.now(timezone.utc)
        created_at = now.isoformat()
        expires_at = (now + timedelta(days=ttl_days)).isoformat()

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT cache_key FROM search_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE search_cache
                    SET search_query = ?, response = ?, search_ok = ?,
                        expires_at = ?, created_at = ?
                    WHERE cache_key = ?
                    """,
                    (search_query, response, int(search_ok), expires_at, created_at, cache_key),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO search_cache
                        (cache_key, search_query, response, search_ok, created_at, expires_at, hit_count)
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                    """,
                    (cache_key, search_query, response, int(search_ok), created_at, expires_at),
                )

            conn.execute(
                """
                INSERT OR IGNORE INTO search_cache_user_queries (cache_key, user_query, added_at)
                VALUES (?, ?, ?)
                """,
                (cache_key, user_query, created_at),
            )

            uq_count = conn.execute(
                "SELECT COUNT(*) AS c FROM search_cache_user_queries WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
            if uq_count and int(uq_count["c"]) > max_user_queries:
                conn.execute(
                    """
                    DELETE FROM search_cache_user_queries
                    WHERE rowid IN (
                        SELECT rowid FROM search_cache_user_queries
                        WHERE cache_key = ?
                        ORDER BY added_at ASC
                        LIMIT ?
                    )
                    """,
                    (cache_key, int(uq_count["c"]) - max_user_queries),
                )

    def record_hit(self, cache_key: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE search_cache SET hit_count = hit_count + 1 WHERE cache_key = ?",
                (cache_key,),
            )

    def delete_by_key(self, cache_key: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM search_cache WHERE cache_key = ?", (cache_key,))
            return cur.rowcount > 0

    def prune_expired(self) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM search_cache WHERE expires_at <= ?",
                (self._now_iso(),),
            )
            return cur.rowcount

    def prune_overflow(self, max_entries: int) -> int:
        if max_entries <= 0:
            return 0
        with self._connect() as conn:
            count_row = conn.execute("SELECT COUNT(*) AS c FROM search_cache").fetchone()
            total = int(count_row["c"]) if count_row else 0
            overflow = total - max_entries
            if overflow <= 0:
                return 0
            keys = conn.execute(
                """
                SELECT cache_key FROM search_cache
                ORDER BY hit_count ASC, created_at ASC
                LIMIT ?
                """,
                (overflow,),
            ).fetchall()
            deleted = 0
            for row in keys:
                conn.execute("DELETE FROM search_cache WHERE cache_key = ?", (row["cache_key"],))
                deleted += 1
            return deleted

    def migrate_from_json(self, json_path: Path) -> int:
        """一次性从旧版 JSON 缓存迁移到 SQLite。"""
        if not json_path.is_file():
            return 0
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("JSON 缓存迁移读取失败: {}", exc)
            return 0

        migrated = 0
        for item in raw.get("entries", []):
            user_q = str(item.get("user_query", "")).strip()
            search_q = str(item.get("search_query", "")).strip() or user_q
            response = str(item.get("response", "")).strip()
            if not user_q or not response:
                continue
            cache_key = search_q  # 由上层 normalize；此处先用原始 search_q，迁移后由 SearchCache 处理
            try:
                self.upsert(
                    cache_key=cache_key.lower(),  # 粗略归一；SearchCache.migrate 会再处理
                    search_query=search_q,
                    response=response,
                    user_query=user_q,
                    search_ok=True,
                    ttl_days=7,
                    max_user_queries=5,
                )
                migrated += 1
            except Exception as exc:
                logger.warning("迁移条目失败: {}", exc)

        if migrated:
            backup = json_path.with_suffix(".json.bak")
            try:
                json_path.rename(backup)
                logger.info("已迁移 {} 条 JSON 缓存至 SQLite，原文件备份为 {}", migrated, backup.name)
            except Exception as exc:
                logger.warning("JSON 缓存备份失败: {}", exc)
        return migrated

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
