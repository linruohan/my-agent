"""定时任务数据模型与 SQLite 存储。"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.database import app_db_path
from src.database.schemas.cron_jobs import SCHEMA
from src.infra.sqlite_store import ReusableSqliteStore


@dataclass
class CronJob:
    id: str
    name: str
    action_type: str
    action: dict[str, Any]
    schedule: dict[str, Any]
    delivery: str
    enabled: bool
    last_run_at: str | None
    next_run_at: str | None
    last_result: str | None
    created_at: str
    updated_at: str


class CronJobStore(ReusableSqliteStore):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(db_path or app_db_path(), foreign_keys=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _row_to_job(row) -> CronJob:
        return CronJob(
            id=row["id"],
            name=row["name"],
            action_type=row["action_type"],
            action=json.loads(row["action_json"]),
            schedule=json.loads(row["schedule_json"]),
            delivery=row["delivery"] or "toast",
            enabled=bool(row["enabled"]),
            last_run_at=row["last_run_at"],
            next_run_at=row["next_run_at"],
            last_result=row["last_result"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def add(
        self,
        *,
        name: str,
        action_type: str,
        action: dict[str, Any],
        schedule: dict[str, Any],
        delivery: str = "toast",
        next_run_at: str | None = None,
    ) -> CronJob:
        jid = str(uuid.uuid4())
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cron_jobs
                (id, name, action_type, action_json, schedule_json, delivery,
                 enabled, next_run_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    jid,
                    name.strip() or "未命名任务",
                    action_type,
                    json.dumps(action, ensure_ascii=False),
                    json.dumps(schedule, ensure_ascii=False),
                    delivery,
                    next_run_at,
                    now,
                    now,
                ),
            )
        job = self.get(jid)
        assert job is not None
        return job

    def get(self, job_id: str) -> CronJob | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM cron_jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def list_all(self, *, enabled_only: bool = False) -> list[CronJob]:
        sql = "SELECT * FROM cron_jobs"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY created_at ASC"
        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [self._row_to_job(r) for r in rows]

    def due_jobs(self, now_iso: str) -> list[CronJob]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM cron_jobs
                WHERE enabled = 1 AND next_run_at IS NOT NULL AND next_run_at <= ?
                ORDER BY next_run_at ASC
                """,
                (now_iso,),
            ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def earliest_next_run(self) -> str | None:
        """最近一次待执行任务的 next_run_at（ISO），无则 None。"""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT MIN(next_run_at) AS n FROM cron_jobs
                WHERE enabled = 1 AND next_run_at IS NOT NULL AND next_run_at != ''
                """
            ).fetchone()
        val = row["n"] if row else None
        return str(val) if val else None

    def update_run(
        self,
        job_id: str,
        *,
        last_run_at: str,
        next_run_at: str | None,
        last_result: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE cron_jobs
                SET last_run_at = ?, next_run_at = ?, last_result = ?, updated_at = ?
                WHERE id = ?
                """,
                (last_run_at, next_run_at, last_result[:2000], self._now(), job_id),
            )

    def set_enabled(self, job_id: str, enabled: bool) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE cron_jobs SET enabled = ?, updated_at = ? WHERE id = ?",
                (1 if enabled else 0, self._now(), job_id),
            )
            return cur.rowcount > 0

    def delete(self, job_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM cron_jobs WHERE id = ?", (job_id,))
            return cur.rowcount > 0

    def set_next_run(self, job_id: str, next_run_at: str | None) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE cron_jobs SET next_run_at = ?, updated_at = ? WHERE id = ?",
                (next_run_at, self._now(), job_id),
            )
            return cur.rowcount > 0
