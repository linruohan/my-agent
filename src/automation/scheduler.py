"""后台定时任务调度服务。"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable

from loguru import logger

from src.automation.executor import advance_job_schedule, execute_cron_job
from src.automation.delivery import deliver_cron_result
from src.automation.schedule import compute_next_run
from src.automation.store import CronJob, CronJobStore

_active_scheduler: CronSchedulerService | None = None
_active_lock = threading.Lock()


def notify_cron_schedule_changed() -> None:
    """任务增删/改期后唤醒调度器，避免空等满 interval。"""
    with _active_lock:
        svc = _active_scheduler
    if svc is not None:
        svc.wake()


class CronSchedulerService:
    """轮询 cron_jobs，按最近到期时间自适应休眠。"""

    def __init__(
        self,
        store: CronJobStore | None = None,
        interval_sec: float = 30.0,
    ) -> None:
        self.store = store or CronJobStore()
        self.interval_sec = interval_sec
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._graph_getter: Callable[[], Any | None] | None = None
        self._on_deliver: Callable[[CronJob, str], None] | None = None
        self._gateway_deliver: Callable[[str, str, str], None] | None = None

    def set_graph_getter(self, getter: Callable[[], Any | None]) -> None:
        self._graph_getter = getter

    def set_delivery_handler(self, handler: Callable[[CronJob, str], None]) -> None:
        self._on_deliver = handler

    def set_gateway_deliver(self, handler: Callable[[str, str, str], None]) -> None:
        self._gateway_deliver = handler

    def wake(self) -> None:
        self._wake.set()

    def start(self) -> None:
        global _active_scheduler
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._wake.clear()
        with _active_lock:
            _active_scheduler = self
        self._thread = threading.Thread(target=self._loop, daemon=True, name="cron-scheduler")
        self._thread.start()

    def stop(self) -> None:
        global _active_scheduler
        self._stop.set()
        self._wake.set()
        with _active_lock:
            if _active_scheduler is self:
                _active_scheduler = None

    def tick(self, now: datetime | None = None) -> None:
        now_dt = now or datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        for job in self.store.due_jobs(now_iso):
            self._run_job(job, now_iso)

    def _run_job(self, job: CronJob, now_iso: str) -> None:
        graph = self._graph_getter() if self._graph_getter else None

        def deliver(j: CronJob, result: str) -> None:
            deliver_cron_result(
                j,
                result,
                gateway_deliver=self._gateway_deliver,
                session_handler=self._on_deliver,
            )

        result = execute_cron_job(job, graph=graph, on_deliver=deliver)
        next_iso = advance_job_schedule(job, now_iso=now_iso)
        self.store.update_run(
            job.id,
            last_run_at=now_iso,
            next_run_at=next_iso,
            last_result=result,
        )
        logger.info("定时任务「{}」完成，下次: {}", job.name, next_iso or "无")

    def _next_sleep_sec(self) -> float:
        """按最近 next_run_at 计算休眠，夹在 [1, interval_sec]。"""
        nxt = self.store.earliest_next_run()
        if not nxt:
            return self.interval_sec
        try:
            target = datetime.fromisoformat(nxt)
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            delta = (target - datetime.now(timezone.utc)).total_seconds()
            if delta <= 0:
                return 0.05
            return max(1.0, min(float(self.interval_sec), delta + 0.05))
        except ValueError:
            return self.interval_sec

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                logger.exception("定时调度轮询失败")
            sleep_for = self._next_sleep_sec()
            self._wake.clear()
            # stop 或 wake 任一触发即醒来
            self._wake.wait(timeout=sleep_for)
            if self._stop.is_set():
                break

    def bootstrap_next_runs(self) -> None:
        """为缺少 next_run_at 的已启用任务计算首次运行时间。"""
        for job in self.store.list_all(enabled_only=True):
            if job.next_run_at:
                continue
            nxt = compute_next_run(job.schedule)
            if nxt:
                self.store.set_next_run(job.id, nxt.isoformat())
        notify_cron_schedule_changed()
