"""SessionStore — 基于 ReusableSqliteStore。"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.infra.paths import DATA_DIR
from src.infra.sqlite_store import ReusableSqliteStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    thread_id  TEXT NOT NULL,
    title      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS session_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    seq        INTEGER NOT NULL,
    event_json TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_session_messages_sid ON session_messages(session_id, seq);
"""


@dataclass
class SessionInfo:
    id: str
    thread_id: str
    title: str
    created_at: str
    updated_at: str


class SessionStore(ReusableSqliteStore):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(db_path or (DATA_DIR / "sessions.db"), foreign_keys=True)
        self._init_schema()
        self._ensure_default()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _ensure_default(self) -> None:
        if self.list_sessions():
            return
        self.create_session("当前会话")

    def list_sessions(self) -> list[SessionInfo]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, thread_id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
        return [SessionInfo(**dict(r)) for r in rows]

    def create_session(self, title: str = "新会话") -> SessionInfo:
        sid = str(uuid.uuid4())
        tid = str(uuid.uuid4())
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, thread_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (sid, tid, title.strip() or "新会话", now, now),
            )
        return SessionInfo(id=sid, thread_id=tid, title=title.strip() or "新会话", created_at=now, updated_at=now)

    def get(self, session_id: str) -> SessionInfo | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, thread_id, title, created_at, updated_at FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return SessionInfo(**dict(row)) if row else None

    def rename(self, session_id: str, title: str) -> bool:
        title = title.strip()
        if not title:
            return False
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title, self._now(), session_id),
            )
            return cur.rowcount > 0

    def delete(self, session_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cur.rowcount > 0

    def touch(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (self._now(), session_id))

    def append_event(self, session_id: str, event: dict[str, Any]) -> None:
        now = self._now()
        payload = json.dumps(event, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO session_messages (session_id, seq, event_json)
                VALUES (
                    ?,
                    (SELECT COALESCE(MAX(seq), 0) + 1 FROM session_messages WHERE session_id = ?),
                    ?
                )
                """,
                (session_id, session_id, payload),
            )
            conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))

    def load_events(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT event_json FROM session_messages WHERE session_id = ? ORDER BY seq ASC",
                (session_id,),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            try:
                events.append(json.loads(row["event_json"]))
            except json.JSONDecodeError:
                continue
        return events

    def clear_messages(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM session_messages WHERE session_id = ?", (session_id,))
