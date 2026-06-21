"""后台轮询：任务提醒与重复任务到期调度。"""

from __future__ import annotations

import threading
from datetime import datetime

from loguru import logger

from src.tools.task.notify import notify_task, send_task_toast
from src.tools.task.repeat import advance_repeat_task
from src.tools.task.store import TaskStore


class TaskReminderService:
    """后台轮询任务提醒与重复任务调度。"""

    def __init__(self, store: TaskStore | None = None, interval_sec: float = 60.0) -> None:
        self.store = store or TaskStore()
        self.interval_sec = interval_sec
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="task-reminder")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def tick(self, now: datetime | None = None) -> None:
        """执行一次调度（便于测试）。"""
        now = now or datetime.now().astimezone()
        self._process_reminders(now)
        self._process_due_tasks(now)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                logger.exception("任务调度轮询失败")
            self._stop.wait(self.interval_sec)

    def _process_reminders(self, now: datetime) -> None:
        for task in self.store.due_for_reminder(now):
            if notify_task(task, kind="reminder"):
                self.store.mark_reminded(task.id)

    def _process_due_tasks(self, now: datetime) -> None:
        for task in self.store.due_for_due(now):
            notify_task(task, kind="due")
            if task.repeat_rule:
                outcome = advance_repeat_task(self.store, task, now=now)
                logger.debug("重复任务 #{} 调度结果: {}", task.id, outcome)
            else:
                self.store.update(task.id, status="expired")
