"""耗时指标持久化（SQLite JSONL 式查询）。"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.infra.paths import DATA_DIR
from src.infra.sqlite_store import ReusableSqliteStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS timing_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    label       TEXT NOT NULL,
    elapsed_ms  INTEGER NOT NULL,
    fields_json TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_timing_label_time ON timing_events(label, created_at);
"""

_MAX_ROWS = 10_000


def metrics_enabled() -> bool:
    return os.environ.get("AGENT_METRICS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


class MetricsStore(ReusableSqliteStore):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(db_path or (DATA_DIR / "metrics.db"))
        self._write_lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def record_timing(self, label: str, elapsed_ms: int, fields: dict[str, Any] | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(fields or {}, ensure_ascii=False)
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO timing_events (label, elapsed_ms, fields_json, created_at) VALUES (?, ?, ?, ?)",
                    (label, elapsed_ms, payload, now),
                )
                row = conn.execute("SELECT COUNT(*) AS c FROM timing_events").fetchone()
                overflow = int(row["c"]) - _MAX_ROWS if row else 0
                if overflow > 0:
                    conn.execute(
                        """
                        DELETE FROM timing_events WHERE id IN (
                            SELECT id FROM timing_events ORDER BY id ASC LIMIT ?
                        )
                        """,
                        (overflow,),
                    )

    def summarize(self, label: str | None = None, *, limit: int = 500) -> dict[str, Any]:
        with self._connect() as conn:
            if label:
                rows = conn.execute(
                    """
                    SELECT elapsed_ms FROM timing_events
                    WHERE label = ?
                    ORDER BY id DESC LIMIT ?
                    """,
                    (label, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT elapsed_ms FROM timing_events ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        values = sorted(int(r["elapsed_ms"]) for r in rows)
        if not values:
            return {"count": 0, "avg_ms": 0, "p95_ms": 0}
        count = len(values)
        avg = sum(values) // count
        p95_idx = min(count - 1, int(count * 0.95))
        return {"count": count, "avg_ms": avg, "p95_ms": values[p95_idx]}

    def labels(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT label FROM timing_events ORDER BY label"
            ).fetchall()
        return [str(r["label"]) for r in rows]


_store: MetricsStore | None = None
_store_lock = threading.Lock()


def get_metrics_store() -> MetricsStore:
    global _store
    with _store_lock:
        if _store is None:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            _store = MetricsStore()
        return _store


def record_timing(label: str, elapsed_ms: int, fields: dict[str, Any] | None = None) -> None:
    if not metrics_enabled():
        return
    try:
        get_metrics_store().record_timing(label, elapsed_ms, fields)
    except Exception:
        pass


def close_metrics_store() -> None:
    global _store
    with _store_lock:
        if _store is not None:
            _store.close()
            _store = None
