"""SessionStore — 基于 ReusableSqliteStore。"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from src.database import app_db_path
from src.database.schemas.sessions import SCHEMA
from src.infra.sqlite_store import ReusableSqliteStore

_DEFAULT_EMPTY_TITLES = {"新会话", "当前会话"}


@dataclass
class SessionInfo:
    id: str
    thread_id: str
    title: str
    created_at: str
    updated_at: str


def _valid_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class SessionStore(ReusableSqliteStore):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(db_path or app_db_path(), foreign_keys=True)
        self._init_schema()
        self._repair_sessions()
        self._ensure_default()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            self._ensure_next_seq_column(conn)

    @staticmethod
    def _ensure_next_seq_column(conn) -> None:
        """兼容旧库：补 next_seq，并按已有消息回填。"""
        cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        if "next_seq" not in cols:
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN next_seq INTEGER NOT NULL DEFAULT 0"
            )
        conn.execute(
            """
            UPDATE sessions
            SET next_seq = (
                SELECT COALESCE(MAX(m.seq), 0)
                FROM session_messages m
                WHERE m.session_id = sessions.id
            )
            WHERE next_seq < (
                SELECT COALESCE(MAX(m.seq), 0)
                FROM session_messages m
                WHERE m.session_id = sessions.id
            )
            """
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _repair_sessions(self) -> None:
        """修复 id 为空的历史脏数据，并清理无消息的空会话。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT rowid, id, thread_id, title, created_at, updated_at FROM sessions"
            ).fetchall()
            if not rows:
                return

            used_ids: set[str] = set()
            for row in rows:
                sid = _valid_id(row["id"])
                if sid:
                    used_ids.add(sid)

            repaired = 0
            removed = 0
            for row in rows:
                rowid = int(row["rowid"])
                sid = _valid_id(row["id"])
                thread_id = _valid_id(row["thread_id"]) or str(uuid.uuid4())
                title = (row["title"] or "").strip() or "新会话"

                msg_count = 0
                if sid:
                    msg_count = int(
                        conn.execute(
                            "SELECT COUNT(*) AS c FROM session_messages WHERE session_id = ?",
                            (sid,),
                        ).fetchone()["c"]
                    )
                if msg_count == 0:
                    msg_count = int(
                        conn.execute(
                            "SELECT COUNT(*) AS c FROM session_messages WHERE session_id = ?",
                            (thread_id,),
                        ).fetchone()["c"]
                    )

                # 无 id 且无消息的占位会话：直接删除
                if not sid and msg_count == 0 and title in _DEFAULT_EMPTY_TITLES:
                    conn.execute("DELETE FROM sessions WHERE rowid = ?", (rowid,))
                    removed += 1
                    continue

                if sid:
                    continue

                # 用 thread_id 回填 id；冲突则换新 uuid
                new_id = thread_id if thread_id not in used_ids else str(uuid.uuid4())
                while new_id in used_ids:
                    new_id = str(uuid.uuid4())
                used_ids.add(new_id)

                conn.execute(
                    "UPDATE sessions SET id = ?, thread_id = ? WHERE rowid = ?",
                    (new_id, thread_id, rowid),
                )
                if thread_id != new_id:
                    conn.execute(
                        "UPDATE session_messages SET session_id = ? WHERE session_id = ?",
                        (new_id, thread_id),
                    )
                repaired += 1

            # 再清一轮：合法 id、默认标题、无消息的冗余空会话（至少留 1 个）
            keep_rows = conn.execute(
                "SELECT rowid, id, title FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
            survivors = len(keep_rows)
            for row in keep_rows:
                if survivors <= 1:
                    break
                sid = _valid_id(row["id"])
                title = (row["title"] or "").strip() or "新会话"
                if not sid or title not in _DEFAULT_EMPTY_TITLES:
                    continue
                msg_count = int(
                    conn.execute(
                        "SELECT COUNT(*) AS c FROM session_messages WHERE session_id = ?",
                        (sid,),
                    ).fetchone()["c"]
                )
                if msg_count > 0:
                    continue
                conn.execute("DELETE FROM sessions WHERE rowid = ?", (int(row["rowid"]),))
                survivors -= 1
                removed += 1

            if repaired or removed:
                logger.info("会话修复完成: repaired={}, removed={}", repaired, removed)

    def _ensure_default(self) -> None:
        if self.list_sessions():
            return
        self.create_session("当前会话")

    def list_sessions(self) -> list[SessionInfo]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, thread_id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
        out: list[SessionInfo] = []
        for r in rows:
            data = dict(r)
            sid = _valid_id(data.get("id"))
            if not sid:
                continue
            data["id"] = sid
            data["thread_id"] = _valid_id(data.get("thread_id")) or sid
            data["title"] = (data.get("title") or "").strip() or "新会话"
            out.append(SessionInfo(**data))
        return out

    def create_session(self, title: str = "新会话") -> SessionInfo:
        sid = str(uuid.uuid4())
        tid = str(uuid.uuid4())
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, thread_id, title, created_at, updated_at, next_seq) "
                "VALUES (?, ?, ?, ?, ?, 0)",
                (sid, tid, title.strip() or "新会话", now, now),
            )
        return SessionInfo(
            id=sid,
            thread_id=tid,
            title=title.strip() or "新会话",
            created_at=now,
            updated_at=now,
        )

    def get(self, session_id: str) -> SessionInfo | None:
        sid = _valid_id(session_id)
        if not sid:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, thread_id, title, created_at, updated_at FROM sessions WHERE id = ?",
                (sid,),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["id"] = _valid_id(data.get("id")) or sid
        data["thread_id"] = _valid_id(data.get("thread_id")) or data["id"]
        data["title"] = (data.get("title") or "").strip() or "新会话"
        return SessionInfo(**data)

    def rename(self, session_id: str, title: str) -> bool:
        sid = _valid_id(session_id)
        title = title.strip()
        if not sid or not title:
            return False
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title, self._now(), sid),
            )
            return cur.rowcount > 0

    def delete(self, session_id: str) -> bool:
        sid = _valid_id(session_id)
        if not sid:
            return False
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE id = ?", (sid,))
            return cur.rowcount > 0

    def touch(self, session_id: str) -> None:
        sid = _valid_id(session_id)
        if not sid:
            return
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (self._now(), sid),
            )

    def append_event(self, session_id: str, event: dict[str, Any]) -> int:
        sid = _valid_id(session_id)
        if not sid:
            return 0
        now = self._now()
        payload = json.dumps(event, ensure_ascii=False)
        with self._connect() as conn:
            seq_row = conn.execute(
                """
                UPDATE sessions
                SET next_seq = next_seq + 1, updated_at = ?
                WHERE id = ?
                RETURNING next_seq
                """,
                (now, sid),
            ).fetchone()
            if not seq_row:
                return 0
            seq = int(seq_row["next_seq"])
            cur = conn.execute(
                """
                INSERT INTO session_messages (session_id, seq, event_json)
                VALUES (?, ?, ?)
                """,
                (sid, seq, payload),
            )
            return int(cur.lastrowid or 0)

    def count_events(self, session_id: str) -> int:
        sid = _valid_id(session_id)
        if not sid:
            return 0
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM session_messages WHERE session_id = ?",
                (sid,),
            ).fetchone()
        return int(row["c"]) if row else 0

    def load_events(
        self,
        session_id: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """加载会话事件。limit>0 时只取最近 N 条（按 seq 升序返回）。"""
        sid = _valid_id(session_id)
        if not sid:
            return []
        with self._connect() as conn:
            if limit is not None and limit > 0:
                rows = conn.execute(
                    """
                    SELECT event_json FROM (
                        SELECT seq, event_json FROM session_messages
                        WHERE session_id = ?
                        ORDER BY seq DESC
                        LIMIT ?
                    ) ORDER BY seq ASC
                    """,
                    (sid, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT event_json FROM session_messages WHERE session_id = ? ORDER BY seq ASC",
                    (sid,),
                ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            try:
                events.append(json.loads(row["event_json"]))
            except json.JSONDecodeError:
                continue
        return events

    def clear_messages(self, session_id: str) -> None:
        sid = _valid_id(session_id)
        if not sid:
            return
        with self._connect() as conn:
            conn.execute("DELETE FROM session_messages WHERE session_id = ?", (sid,))
            conn.execute("UPDATE sessions SET next_seq = 0 WHERE id = ?", (sid,))

    def search_messages(self, keyword: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """跨会话搜索用户/助手消息文本。"""
        kw = (keyword or "").strip()
        if not kw:
            return []
        pattern = f"%{kw}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.title AS session_title, m.event_json
                FROM session_messages m
                JOIN sessions s ON s.id = m.session_id
                WHERE m.event_json LIKE ?
                ORDER BY m.id DESC
                LIMIT ?
                """,
                (pattern, max(1, limit * 3)),
            ).fetchall()
        hits: list[dict[str, Any]] = []
        for row in rows:
            try:
                event = json.loads(row["event_json"])
            except json.JSONDecodeError:
                continue
            etype = event.get("type")
            if etype == "user":
                text = str(event.get("content") or event.get("text") or "")
                role = "user"
            elif etype == "assistant_end":
                text = str(event.get("content") or event.get("text") or "")
                role = "assistant"
            else:
                continue
            if kw.lower() not in text.lower():
                continue
            hits.append(
                {
                    "session_title": row["session_title"],
                    "role": role,
                    "text": text,
                }
            )
            if len(hits) >= limit:
                break
        return hits

    def fetch_recent_messages(self, *, limit: int = 400) -> list[dict[str, Any]]:
        """跨会话获取最近的用户/助手消息，供语义检索候选。"""
        cap = max(1, limit)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.title AS session_title, m.event_json
                FROM session_messages m
                JOIN sessions s ON s.id = m.session_id
                ORDER BY m.id DESC
                LIMIT ?
                """,
                (cap * 2,),
            ).fetchall()
        hits: list[dict[str, Any]] = []
        for row in rows:
            try:
                event = json.loads(row["event_json"])
            except json.JSONDecodeError:
                continue
            etype = event.get("type")
            if etype == "user":
                text = str(event.get("content") or event.get("text") or "")
                role = "user"
            elif etype == "assistant_end":
                text = str(event.get("content") or event.get("text") or "")
                role = "assistant"
            else:
                continue
            text = text.strip()
            if not text:
                continue
            hits.append(
                {
                    "session_title": row["session_title"],
                    "role": role,
                    "text": text,
                }
            )
            if len(hits) >= cap:
                break
        return hits

    def fetch_messages_for_index(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """获取候选消息供向量索引（按 message id 升序）。"""
        cap = max(1, limit)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT m.id AS message_id, m.session_id, s.title AS session_title, m.event_json
                FROM session_messages m
                JOIN sessions s ON s.id = m.session_id
                ORDER BY m.id DESC
                LIMIT ?
                """,
                (cap * 3,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                event = json.loads(row["event_json"])
            except json.JSONDecodeError:
                continue
            if event.get("type") not in ("user", "assistant_end"):
                continue
            out.append(
                {
                    "message_id": int(row["message_id"]),
                    "session_id": row["session_id"],
                    "session_title": row["session_title"],
                    "event": event,
                }
            )
            if len(out) >= cap:
                break
        return out
