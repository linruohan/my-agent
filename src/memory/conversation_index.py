"""历史对话向量索引（增量持久化，加速语义检索）。"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from src.infra.paths import DATA_DIR
from src.infra.sqlite_store import ReusableSqliteStore
from src.memory.conversation_search import _cosine, _embeddings, conversation_search_config
from src.ui.session_store import SessionStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversation_vectors (
    message_id     INTEGER PRIMARY KEY,
    session_id     TEXT NOT NULL,
    session_title  TEXT NOT NULL,
    role           TEXT NOT NULL,
    text           TEXT NOT NULL,
    embedding_json TEXT NOT NULL,
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conv_vec_created ON conversation_vectors(message_id DESC);
CREATE TABLE IF NOT EXISTS conversation_index_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_index_lock = threading.Lock()
_shared_index: ConversationIndex | None = None


class ConversationIndex(ReusableSqliteStore):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(db_path or (DATA_DIR / "conversation_index.db"))
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def has_entry(self, message_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM conversation_vectors WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        return row is not None

    def upsert(
        self,
        *,
        message_id: int,
        session_id: str,
        session_title: str,
        role: str,
        text: str,
        embedding: list[float],
    ) -> None:
        body = (text or "").strip()[:1500]
        if not body:
            return
        payload = json.dumps(embedding, ensure_ascii=False)
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversation_vectors
                (message_id, session_id, session_title, role, text, embedding_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    session_id=excluded.session_id,
                    session_title=excluded.session_title,
                    role=excluded.role,
                    text=excluded.text,
                    embedding_json=excluded.embedding_json,
                    created_at=excluded.created_at
                """,
                (message_id, session_id, session_title, role, body, payload, now),
            )
            conn.execute(
                """
                INSERT INTO conversation_index_meta (key, value) VALUES ('last_message_id', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (str(message_id),),
            )

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM conversation_vectors").fetchone()
        return int(row["n"]) if row else 0

    def search(
        self,
        query_vec: list[float],
        *,
        limit: int = 10,
        threshold: float = 0.35,
        pool: int | None = None,
    ) -> list[dict[str, Any]]:
        cfg = conversation_search_config()
        cap = pool if pool is not None else int(cfg.get("index_search_pool", 2000) or 2000)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT session_title, role, text, embedding_json
                FROM conversation_vectors
                ORDER BY message_id DESC
                LIMIT ?
                """,
                (max(limit, cap),),
            ).fetchall()
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            try:
                vec = json.loads(row["embedding_json"])
            except (json.JSONDecodeError, TypeError):
                continue
            score = _cosine(query_vec, vec)
            if score >= threshold:
                scored.append(
                    (
                        score,
                        {
                            "session_title": row["session_title"],
                            "role": row["role"],
                            "text": row["text"],
                            "score": round(score, 3),
                        },
                    )
                )
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[: max(1, limit)]]


def shared_conversation_index() -> ConversationIndex:
    global _shared_index
    if _shared_index is None:
        _shared_index = ConversationIndex()
    return _shared_index


def _event_to_index_fields(event: dict[str, Any]) -> tuple[str, str] | None:
    etype = event.get("type")
    if etype == "user":
        text = str(event.get("content") or event.get("text") or "").strip()
        return ("user", text) if text else None
    if etype == "assistant_end":
        text = str(event.get("content") or event.get("text") or "").strip()
        return ("assistant", text) if text else None
    return None


def index_chat_message(
    *,
    message_id: int,
    session_id: str,
    session_title: str,
    event: dict[str, Any],
    index: ConversationIndex | None = None,
) -> bool:
    cfg = conversation_search_config()
    if not cfg.get("index_enabled", True):
        return False
    fields = _event_to_index_fields(event)
    if not fields:
        return False
    role, text = fields
    idx = index or shared_conversation_index()
    if idx.has_entry(message_id):
        return False
    try:
        vec = _embeddings().embed_documents([text[:1500]])[0]
    except Exception:
        logger.exception("对话索引 Embedding 失败 message_id={}", message_id)
        return False
    idx.upsert(
        message_id=message_id,
        session_id=session_id,
        session_title=session_title,
        role=role,
        text=text,
        embedding=vec,
    )
    return True


def backfill_conversation_index(
    *,
    batch_size: int | None = None,
    store: SessionStore | None = None,
    index: ConversationIndex | None = None,
) -> int:
    """索引尚未入库的历史消息，返回本次新增条数。"""
    cfg = conversation_search_config()
    if not cfg.get("index_enabled", True):
        return 0
    size = batch_size if batch_size is not None else int(cfg.get("rebuild_batch_size", 100) or 100)
    session_store = store or SessionStore()
    idx = index or shared_conversation_index()
    rows = session_store.fetch_messages_for_index(limit=max(1, size))
    added = 0
    for row in rows:
        if idx.has_entry(row["message_id"]):
            continue
        event = row.get("event") or {}
        fields = _event_to_index_fields(event)
        if not fields:
            continue
        role, text = fields
        try:
            vec = _embeddings().embed_documents([text[:1500]])[0]
        except Exception:
            logger.exception("对话索引回填失败 message_id={}", row["message_id"])
            break
        idx.upsert(
            message_id=row["message_id"],
            session_id=row["session_id"],
            session_title=row["session_title"],
            role=role,
            text=text,
            embedding=vec,
        )
        added += 1
    return added


def schedule_index_chat_message(
    *,
    message_id: int,
    session_id: str,
    session_title: str,
    event: dict[str, Any],
) -> None:
    """后台线程增量索引，避免阻塞 UI。"""

    def worker() -> None:
        with _index_lock:
            index_chat_message(
                message_id=message_id,
                session_id=session_id,
                session_title=session_title,
                event=event,
            )

    threading.Thread(target=worker, daemon=True, name="conv-index").start()
