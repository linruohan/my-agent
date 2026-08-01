from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from src.automation.executor import execute_cron_job
from src.automation.schedule import compute_next_run, format_schedule
from src.automation.scheduler import CronSchedulerService
from src.automation.store import CronJobStore
from src.memory.context_files import (
    build_memory_prompt_block,
    ensure_context_files,
    memory_file_path,
    user_file_path,
    write_context_file,
)


def test_ensure_context_files(tmp_path, monkeypatch):
    monkeypatch.setattr("src.memory.context_files.workspace_dir", lambda: tmp_path)
    ensure_context_files()
    assert user_file_path().is_file()
    assert memory_file_path().is_file()


def test_build_memory_prompt_block(tmp_path, monkeypatch):
    monkeypatch.setattr("src.memory.context_files.workspace_dir", lambda: tmp_path)
    ensure_context_files()
    write_context_file(user_file_path(), "## 偏好\n- 简洁", mode="replace")
    block = build_memory_prompt_block()
    assert "USER.md" in block
    assert "简洁" in block
    assert "update_agent_memory" in block


def test_compute_next_run_interval():
    now = datetime(2026, 6, 24, 10, 0, tzinfo=timezone.utc)
    nxt = compute_next_run({"type": "interval", "minutes": 30}, after=now)
    assert nxt == now + timedelta(minutes=30)


def test_compute_next_run_daily():
    now = datetime(2026, 6, 24, 10, 0, tzinfo=timezone.utc).astimezone()
    nxt = compute_next_run({"type": "daily", "hour": 9, "minute": 0}, after=now)
    assert nxt.hour == 9
    assert nxt.minute == 0
    assert nxt.date() > now.date()


def test_cron_job_lifecycle(tmp_path):
    db = tmp_path / "cron.db"
    store = CronJobStore(db)
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    job = store.add(
        name="测试提醒",
        action_type="notify",
        action={"message": "hello"},
        schedule={"type": "interval", "minutes": 60},
        next_run_at=past,
    )
    due = store.due_jobs(datetime.now(timezone.utc).isoformat())
    assert any(j.id == job.id for j in due)
    assert format_schedule(job.schedule).startswith("每")


def test_execute_notify_job(tmp_path):
    store = CronJobStore(tmp_path / "cron.db")
    job = store.add(
        name="ping",
        action_type="notify",
        action={"message": "定时消息"},
        schedule={"type": "interval", "minutes": 1},
    )
    result = execute_cron_job(job)
    assert "定时消息" in result


def test_scheduler_tick_runs_due_job(tmp_path):
    store = CronJobStore(tmp_path / "cron.db")
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    store.add(
        name="due",
        action_type="notify",
        action={"message": "done"},
        schedule={"type": "interval", "minutes": 10},
        next_run_at=past,
        delivery="session",
    )
    svc = CronSchedulerService(store, interval_sec=1)
    delivered: list[str] = []

    def on_deliver(job, result):
        delivered.append(result)

    svc.set_delivery_handler(on_deliver)
    with patch("src.automation.delivery.send_cron_toast", return_value=True):
        svc.tick()
    assert delivered and "done" in delivered[0]


def test_earliest_next_run_and_adaptive_sleep(tmp_path):
    store = CronJobStore(tmp_path / "cron.db")
    future = (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat()
    store.add(
        name="soon",
        action_type="notify",
        action={"message": "x"},
        schedule={"type": "interval", "minutes": 10},
        next_run_at=future,
    )
    assert store.earliest_next_run() == future
    svc = CronSchedulerService(store, interval_sec=30)
    sleep_for = svc._next_sleep_sec()
    assert 1.0 <= sleep_for <= 30.0
    assert sleep_for <= 6.0
