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


class CronSchedulerService:
    """轮询 cron_jobs.db，到期执行任务并投递结果。"""

    def __init__(
        self,
        store: CronJobStore | None = None,
        interval_sec: float = 30.0,
    ) -> None:
        self.store = store or CronJobStore()
        self.interval_sec = interval_sec
        self._stop = threading.Event()
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

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="cron-scheduler")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

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

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                logger.exception("定时调度轮询失败")
            self._stop.wait(self.interval_sec)

    def bootstrap_next_runs(self) -> None:
        """为缺少 next_run_at 的已启用任务计算首次运行时间。"""
        for job in self.store.list_all(enabled_only=True):
            if job.next_run_at:
                continue
            nxt = compute_next_run(job.schedule)
            if nxt:
                self.store.set_next_run(job.id, nxt.isoformat())
