"""Gateway 消息收件箱（跨通道入站/出站）。"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.database import app_db_path
from src.database.schemas.gateway import SCHEMA
from src.infra.sqlite_store import ReusableSqliteStore


@dataclass
class GatewayMessage:
    id: str
    source: str
    chat_id: str
    text: str
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""


class GatewayInbox(ReusableSqliteStore):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(db_path or app_db_path(), foreign_keys=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def push_inbound(
        self,
        source: str,
        chat_id: str,
        text: str,
        *,
        meta: dict[str, Any] | None = None,
    ) -> GatewayMessage:
        mid = str(uuid.uuid4())
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO gateway_inbound (id, source, chat_id, text, meta_json, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
                """,
                (mid, source, chat_id, text, json.dumps(meta or {}, ensure_ascii=False), now),
            )
        return GatewayMessage(id=mid, source=source, chat_id=chat_id, text=text, meta=meta or {}, created_at=now)

    def pop_inbound(self) -> GatewayMessage | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, source, chat_id, text, meta_json, created_at
                FROM gateway_inbound
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE gateway_inbound SET status = 'processing' WHERE id = ?",
                (row["id"],),
            )
        meta = {}
        try:
            meta = json.loads(row["meta_json"] or "{}")
        except json.JSONDecodeError:
            pass
        return GatewayMessage(
            id=row["id"],
            source=row["source"],
            chat_id=row["chat_id"],
            text=row["text"],
            meta=meta,
            created_at=row["created_at"],
        )

    def mark_inbound_done(self, message_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE gateway_inbound SET status = 'done' WHERE id = ?",
                (message_id,),
            )

    def mark_inbound_failed(self, message_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE gateway_inbound SET status = 'failed' WHERE id = ?",
                (message_id,),
            )

    def mark_inbound_pending(self, message_id: str) -> None:
        """将 processing 入站恢复为 pending（Agent 忙时重新排队）。"""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE gateway_inbound
                SET status = 'pending'
                WHERE id = ? AND status = 'processing'
                """,
                (message_id,),
            )

    def count_pending_inbound(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM gateway_inbound WHERE status = 'pending'"
            ).fetchone()
        return int(row["n"]) if row else 0

    def get_chat_session(self, gateway_key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT session_id FROM gateway_chat_sessions WHERE gateway_key = ?",
                (gateway_key,),
            ).fetchone()
        return str(row["session_id"]) if row else None

    def set_chat_session(self, gateway_key: str, session_id: str) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO gateway_chat_sessions (gateway_key, session_id, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(gateway_key) DO UPDATE SET session_id = excluded.session_id
                """,
                (gateway_key, session_id, now),
            )

    def reclaim_stale_processing(self, *, max_age_sec: float | None = None) -> int:
        """将卡住的 processing 入站恢复为 pending。max_age_sec 为 None 时回收全部（启动用）。"""
        with self._connect() as conn:
            if max_age_sec is None:
                cur = conn.execute(
                    """
                    UPDATE gateway_inbound
                    SET status = 'pending'
                    WHERE status = 'processing'
                    """
                )
            else:
                from datetime import timedelta

                cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max_age_sec)).isoformat()
                cur = conn.execute(
                    """
                    UPDATE gateway_inbound
                    SET status = 'pending'
                    WHERE status = 'processing'
                      AND created_at < ?
                    """,
                    (cutoff,),
                )
        return cur.rowcount or 0

    def push_outbound(self, source: str, chat_id: str, text: str) -> str:
        mid = str(uuid.uuid4())
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO gateway_outbound (id, source, chat_id, text, status, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
                """,
                (mid, source, chat_id, text, now),
            )
        return mid

    def pop_outbound_batch(self, *, limit: int = 20) -> list[GatewayMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, source, chat_id, text, created_at
                FROM gateway_outbound
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            ids = [r["id"] for r in rows]
            if ids:
                conn.executemany(
                    "UPDATE gateway_outbound SET status = 'sent' WHERE id = ?",
                    [(i,) for i in ids],
                )
        return [
            GatewayMessage(
                id=r["id"],
                source=r["source"],
                chat_id=r["chat_id"],
                text=r["text"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def fetch_outbound_pending(self, *, limit: int = 20) -> list[GatewayMessage]:
        """读取待发送出站消息但不改状态（供 HTTP 长轮询）。"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, source, chat_id, text, created_at
                FROM gateway_outbound
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            GatewayMessage(
                id=r["id"],
                source=r["source"],
                chat_id=r["chat_id"],
                text=r["text"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
