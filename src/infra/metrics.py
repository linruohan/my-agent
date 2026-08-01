"""耗时指标持久化（SQLite JSONL 式查询）。"""

from __future__ import annotations

import atexit
import json
import os
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.database.paths import app_db_path
from src.database.schemas.timing_events import SCHEMA
from src.infra.paths import DATA_DIR
from src.infra.sqlite_store import ReusableSqliteStore

_MAX_ROWS = 10_000
_FLUSH_BATCH = 32
_FLUSH_INTERVAL_SEC = 0.5


def metrics_enabled() -> bool:
    # 默认关闭，避免热路径同步写库；需要时设 AGENT_METRICS=1
    return os.environ.get("AGENT_METRICS", "0").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
        "",
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

    def record_timing_batch(
        self,
        items: list[tuple[str, int, dict[str, Any] | None]],
    ) -> None:
        if not items:
            return
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (label, elapsed_ms, json.dumps(fields or {}, ensure_ascii=False), now)
            for label, elapsed_ms, fields in items
        ]
        with self._write_lock:
            with self._connect() as conn:
                conn.executemany(
                    "INSERT INTO timing_events (label, elapsed_ms, fields_json, created_at) VALUES (?, ?, ?, ?)",
                    rows,
                )
                self._approx_rows += len(rows)
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
_pending: queue.Queue[tuple[str, int, dict[str, Any] | None] | None] = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()
_flush_event = threading.Event()


def get_metrics_store() -> MetricsStore:
    global _store
    with _store_lock:
        if _store is None:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            _store = MetricsStore()
        return _store


def _ensure_worker() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        thread = threading.Thread(target=_metrics_worker, name="metrics-flush", daemon=True)
        thread.start()
        _worker_started = True


def _metrics_worker() -> None:
    batch: list[tuple[str, int, dict[str, Any] | None]] = []
    while True:
        try:
            item = _pending.get(timeout=_FLUSH_INTERVAL_SEC)
        except queue.Empty:
            item = None
            if not batch:
                continue

        if item is None and not batch:
            # 显式 flush 哨兵且无积压
            _flush_event.set()
            continue

        if item is not None:
            batch.append(item)

        while len(batch) < _FLUSH_BATCH:
            try:
                nxt = _pending.get_nowait()
            except queue.Empty:
                break
            if nxt is None:
                break
            batch.append(nxt)

        if batch:
            try:
                get_metrics_store().record_timing_batch(batch)
            except Exception:
                from loguru import logger

                logger.debug("批量写入 metrics 失败", exc_info=True)
            batch.clear()
        _flush_event.set()


def flush_metrics() -> None:
    """等待异步队列落盘（查询/导出/测试前调用）。"""
    if not metrics_enabled():
        return
    _ensure_worker()
    _flush_event.clear()
    _pending.put(None)
    _flush_event.wait(timeout=5.0)


def record_timing(label: str, elapsed_ms: int, fields: dict[str, Any] | None = None) -> None:
    if not metrics_enabled():
        return
    try:
        _ensure_worker()
        _pending.put((label, elapsed_ms, fields))
    except Exception:
        from loguru import logger

        logger.debug("记录 metrics 失败 label={}", label, exc_info=True)


def close_metrics_store() -> None:
    global _store
    flush_metrics()
    with _store_lock:
        if _store is not None:
            _store.close()
            _store = None


def export_metrics_csv(path: Path | None = None, *, limit: int = 5000) -> tuple[int, Path]:
    """导出 metrics 为 CSV。返回 (行数, 路径)。"""
    if not metrics_enabled():
        raise RuntimeError("metrics 已关闭（AGENT_METRICS=0）")
    from src.infra.paths import DATA_DIR as data_root

    flush_metrics()
    out = path or (data_root / "metrics_export.csv")
    count = get_metrics_store().export_csv(out, limit=limit)
    return count, out


atexit.register(flush_metrics)
