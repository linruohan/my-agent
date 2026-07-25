"""任务 SQLite 存储（app.db / tasks 表）。"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.database import app_db_path
from src.database.schemas.tasks import SCHEMA
from src.infra.sqlite_store import ReusableSqliteStore

VALID_STATUS = {"pending", "done", "expired", "planned"}


def _load_remind_schedule(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [str(x) for x in data]
    return []


def _load_attachments(raw: str | None) -> list[dict[str, str]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        val = str(item.get("value") or "").strip()
        if not val:
            continue
        kind = str(item.get("type") or "file").lower()
        out.append({"type": "url" if kind == "url" else "file", "value": val})
    return out


@dataclass
class TaskRow:
    id: int
    title: str
    content: str
    due_at: str | None
    repeat_rule: str | None
    remind_at: str | None
    created_at: str
    updated_at: str
    tags: list[str] = field(default_factory=list)
    status: str = "pending"
    owner: str | None = None
    repeat_end: str | None = None
    repeat_count: int = 0
    remind_spec: str | None = None
    remind_schedule: list[str] = field(default_factory=list)
    attachments: list[dict[str, str]] = field(default_factory=list)


class TaskStore(ReusableSqliteStore):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(db_path or app_db_path())
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate_columns(conn)

    @staticmethod
    def _migrate_columns(conn: sqlite3.Connection) -> None:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner TEXT")
        if "repeat_end" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN repeat_end TEXT")
        if "repeat_count" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN repeat_count INTEGER NOT NULL DEFAULT 0")
        if "remind_spec" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN remind_spec TEXT")
        if "remind_schedule" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN remind_schedule TEXT")
        if "attachments" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN attachments TEXT NOT NULL DEFAULT '[]'")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _row_from_db(row: sqlite3.Row) -> TaskRow:
        tags_raw = row["tags"] or "[]"
        try:
            tags = json.loads(tags_raw)
        except json.JSONDecodeError:
            tags = []
        return TaskRow(
            id=int(row["id"]),
            title=row["title"],
            content=row["content"] or "",
            due_at=row["due_at"],
            repeat_rule=row["repeat_rule"],
            remind_at=row["remind_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            tags=[str(t) for t in tags],
            status=row["status"] or "pending",
            owner=row["owner"],
            repeat_end=row["repeat_end"],
            repeat_count=int(row["repeat_count"] or 0),
            remind_spec=row["remind_spec"],
            remind_schedule=_load_remind_schedule(row["remind_schedule"]),
            attachments=_load_attachments(row["attachments"]),
        )

    def add(
        self,
        title: str,
        content: str = "",
        *,
        due_at: str | None = None,
        repeat_rule: str | None = None,
        remind_at: str | None = None,
        tags: list[str] | None = None,
        status: str = "pending",
        created_at: str | None = None,
        owner: str | None = None,
        repeat_end: str | None = None,
        remind_spec: str | None = None,
        remind_schedule: list[str] | None = None,
        attachments: list[dict[str, str]] | None = None,
        repeat_count: int = 0,
    ) -> TaskRow:
        title = (title or "").strip()
        if not title:
            raise ValueError("任务名不能为空")
        status = status if status in VALID_STATUS else "pending"
        now = created_at or self._now()
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        if remind_at is None and remind_spec and due_at and not remind_schedule:
            try:
                due_dt = self._parse_iso(due_at)
                from src.tools.task.defaults import build_remind_schedule

                remind_schedule = build_remind_schedule(due_dt, remind_spec)
                remind_at = remind_schedule[0] if remind_schedule else None
            except ValueError:
                pass
        schedule_json = json.dumps(remind_schedule or [], ensure_ascii=False)
        attachments_json = json.dumps(attachments or [], ensure_ascii=False)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO tasks
                    (title, content, due_at, repeat_rule, remind_at, created_at, updated_at,
                     tags, status, owner, repeat_end, repeat_count, remind_spec, remind_schedule, attachments)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title, content or "", due_at, repeat_rule, remind_at, now, now,
                    tags_json, status, owner, repeat_end, repeat_count, remind_spec,
                    schedule_json, attachments_json,
                ),
            )
            tid = int(cur.lastrowid)
        row = self.get(tid)
        assert row is not None
        return row

    def get(self, task_id: int) -> TaskRow | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_from_db(row) if row else None

    def list_incomplete(self) -> list[TaskRow]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status IN ('pending', 'planned', 'expired')
                ORDER BY id DESC
                """
            ).fetchall()
        return [self._row_from_db(r) for r in rows]

    def list_all(self, *, include_done: bool = False) -> list[TaskRow]:
        with self._connect() as conn:
            if include_done:
                rows = conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM tasks
                    WHERE status IN ('pending', 'planned', 'expired')
                    ORDER BY id DESC
                    """
                ).fetchall()
        return [self._row_from_db(r) for r in rows]

    def search(self, keyword: str) -> list[TaskRow]:
        kw = f"%{keyword.strip()}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE title LIKE ? OR content LIKE ?
                ORDER BY id DESC
                """,
                (kw, kw),
            ).fetchall()
        return [self._row_from_db(r) for r in rows]

    def delete(self, task_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cur.rowcount > 0

    def update_status(self, task_id: int, status: str) -> bool:
        if status not in VALID_STATUS:
            return False
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status, self._now(), task_id),
            )
            return cur.rowcount > 0

    def update(
        self,
        task_id: int,
        *,
        title: str | None = None,
        content: str | None = None,
        due_at: str | None = None,
        repeat_rule: str | None = None,
        remind_at: str | None = None,
        tags: list[str] | None = None,
        status: str | None = None,
        owner: str | None = None,
        repeat_end: str | None = None,
        repeat_count: int | None = None,
        remind_spec: str | None = None,
        remind_schedule: list[str] | None = None,
        attachments: list[dict[str, str]] | None = None,
        clear_remind: bool = False,
        clear_remind_spec: bool = False,
    ) -> bool:
        row = self.get(task_id)
        if not row:
            return False
        fields: dict[str, Any] = {}
        if title is not None:
            title = title.strip()
            if not title:
                raise ValueError("任务名不能为空")
            fields["title"] = title
        if content is not None:
            fields["content"] = content
        if due_at is not None:
            fields["due_at"] = due_at
        if repeat_rule is not None:
            fields["repeat_rule"] = repeat_rule
        if clear_remind:
            fields["remind_at"] = None
            fields["remind_schedule"] = json.dumps([], ensure_ascii=False)
        elif remind_at is not None:
            fields["remind_at"] = remind_at
        if remind_schedule is not None:
            fields["remind_schedule"] = json.dumps(remind_schedule, ensure_ascii=False)
        if tags is not None:
            fields["tags"] = json.dumps(tags, ensure_ascii=False)
        if status is not None:
            if status not in VALID_STATUS:
                raise ValueError(f"无效状态：{status}")
            fields["status"] = status
        if owner is not None:
            fields["owner"] = owner
        if repeat_end is not None:
            fields["repeat_end"] = repeat_end
        if repeat_count is not None:
            fields["repeat_count"] = repeat_count
        if clear_remind_spec:
            fields["remind_spec"] = None
        elif remind_spec is not None:
            fields["remind_spec"] = remind_spec
        if attachments is not None:
            fields["attachments"] = json.dumps(attachments, ensure_ascii=False)
        if not fields:
            return True
        fields["updated_at"] = self._now()
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [task_id]
        with self._connect() as conn:
            cur = conn.execute(f"UPDATE tasks SET {sets} WHERE id = ?", vals)
            return cur.rowcount > 0

    @staticmethod
    def _parse_iso(value: str) -> datetime:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.astimezone()
        return dt

    def due_for_reminder(self, now: datetime | None = None) -> list[TaskRow]:
        now = now or datetime.now().astimezone()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status IN ('pending', 'planned')
                  AND remind_at IS NOT NULL
                """
            ).fetchall()
        due_rows: list[TaskRow] = []
        for r in rows:
            row = self._row_from_db(r)
            if not row.remind_at:
                continue
            try:
                if self._parse_iso(row.remind_at) <= now:
                    due_rows.append(row)
            except ValueError:
                continue
        return sorted(due_rows, key=lambda x: x.remind_at or "")

    def due_for_due(self, now: datetime | None = None) -> list[TaskRow]:
        now = now or datetime.now().astimezone()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status IN ('pending', 'planned')
                  AND due_at IS NOT NULL
                """
            ).fetchall()
        due_rows: list[TaskRow] = []
        for r in rows:
            row = self._row_from_db(r)
            if not row.due_at:
                continue
            try:
                if self._parse_iso(row.due_at) <= now:
                    due_rows.append(row)
            except ValueError:
                continue
        return sorted(due_rows, key=lambda x: x.due_at or "")

    def mark_reminded(self, task_id: int) -> None:
        row = self.get(task_id)
        if not row:
            return
        fired = row.remind_at
        schedule = list(row.remind_schedule or [])
        if fired and fired in schedule:
            schedule = [s for s in schedule if s != fired]
        elif schedule:
            schedule = schedule[1:]
        next_at = min(schedule) if schedule else None
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tasks SET remind_at = ?, remind_schedule = ?, updated_at = ? WHERE id = ?
                """,
                (next_at, json.dumps(schedule, ensure_ascii=False), self._now(), task_id),
            )


def send_windows_toast(title: str, message: str) -> bool:
    from src.tools.task.notify import send_task_toast

    return send_task_toast(title, message)

