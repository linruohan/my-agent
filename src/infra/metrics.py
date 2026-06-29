"""耗时指标持久化（SQLite JSONL 式查询）。"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.database.paths import app_db_path
from src.database.schemas.timing_events import SCHEMA
from src.infra.paths import DATA_DIR
from src.infra.sqlite_store import ReusableSqliteStore

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
        super().__init__(db_path or app_db_path())
        self._write_lock = threading.Lock()
        self._approx_rows = 0
        self._init_schema()
        self._sync_row_count()

    def _sync_row_count(self) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM timing_events").fetchone()
        self._approx_rows = int(row["c"]) if row else 0

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def record_timing(self, label: str, elapsed_ms: int, fields: dict[str, Any] | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(fields or {}, ensure_ascii=False)
        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO timing_events (label, elapsed_ms, fields_json, created_at) VALUES (?, ?, ?, ?)",
                    (label, elapsed_ms, payload, now),
                )
                self._approx_rows += 1
                overflow = self._approx_rows - _MAX_ROWS
                if overflow > 0:
                    conn.execute(
                        """
                        DELETE FROM timing_events WHERE id IN (
                            SELECT id FROM timing_events ORDER BY id ASC LIMIT ?
                        )
                        """,
                        (overflow,),
                    )
                    self._approx_rows -= overflow

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

    def export_csv(self, path: Path, *, limit: int = 5000) -> int:
        """导出最近 timing 记录为 CSV，返回行数。"""
        import csv

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT label, elapsed_ms, fields_json, created_at
                FROM timing_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["label", "elapsed_ms", "fields_json", "created_at"])
            for row in rows:
                writer.writerow([row["label"], row["elapsed_ms"], row["fields_json"], row["created_at"]])
        return len(rows)


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


def export_metrics_csv(path: Path | None = None, *, limit: int = 5000) -> tuple[int, Path]:
    """导出 metrics 为 CSV。返回 (行数, 路径)。"""
    if not metrics_enabled():
        raise RuntimeError("metrics 已关闭（AGENT_METRICS=0）")
    from src.infra.paths import DATA_DIR as data_root

    out = path or (data_root / "metrics_export.csv")
    count = get_metrics_store().export_csv(out, limit=limit)
    return count, out
