"""重复任务调度：推进 due_at / remind_at，判断终止条件。"""

from __future__ import annotations

import calendar
import json
from datetime import datetime, timedelta
from typing import Any

from src.tools.task.defaults import build_remind_schedule
from src.tools.task.store import TaskRow, TaskStore


def decode_repeat_rule(rule: str | None) -> dict[str, Any] | None:
    if not rule:
        return None
    try:
        data = json.loads(rule)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return {
        "every": int(data.get("every") or 1),
        "unit": str(data.get("unit") or "day").lower(),
        "times": int(data.get("times") or 1),
    }


def add_interval(dt: datetime, every: int, unit: str) -> datetime:
    every = max(1, every)
    unit = unit.lower()
    if unit == "day":
        return dt + timedelta(days=every)
    if unit == "week":
        return dt + timedelta(weeks=every)
    if unit == "month":
        month = dt.month - 1 + every
        year = dt.year + month // 12
        month = month % 12 + 1
        day = min(dt.day, calendar.monthrange(year, month)[1])
        return dt.replace(year=year, month=month, day=day)
    if unit == "year":
        year = dt.year + every
        day = min(dt.day, calendar.monthrange(year, dt.month)[1])
        return dt.replace(year=year, day=day)
    raise ValueError(f"未知重复单位：{unit}")


def _parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.astimezone()
    return dt


def _repeat_max_count(row: TaskRow) -> int | None:
    end = (row.repeat_end or "").strip()
    if end.isdigit():
        return int(end)
    if end.lower() == "none" or not end:
        rule = decode_repeat_rule(row.repeat_rule)
        if rule and rule.get("times"):
            return int(rule["times"])
        return None
    return None


def _repeat_end_datetime(row: TaskRow) -> datetime | None:
    end = (row.repeat_end or "").strip()
    if not end or end.lower() == "none" or end.isdigit():
        return None
    try:
        return _parse_iso(end)
    except ValueError:
        return None


def should_complete_repeat(row: TaskRow, *, next_due: datetime, completed_count: int) -> bool:
    max_count = _repeat_max_count(row)
    if max_count is not None and completed_count >= max_count:
        return True
    end_dt = _repeat_end_datetime(row)
    if end_dt is not None and next_due > end_dt:
        return True
    return False


def next_remind_for_task(row: TaskRow, new_due: datetime) -> tuple[str | None, list[str]]:
    if not row.remind_spec:
        return None, []
    schedule = build_remind_schedule(new_due, row.remind_spec)
    return (schedule[0] if schedule else None), schedule


def advance_repeat_task(store: TaskStore, task: TaskRow, *, now: datetime | None = None) -> str:
    """到期后推进重复任务。返回 advanced | completed。"""
    now = now or datetime.now().astimezone()
    rule = decode_repeat_rule(task.repeat_rule)
    if not rule or not task.due_at:
        store.update(task.id, status="expired")
        return "completed"

    due = _parse_iso(task.due_at)
    completed_count = (task.repeat_count or 0) + 1
    next_due = add_interval(due, rule["every"], rule["unit"])

    if should_complete_repeat(task, next_due=next_due, completed_count=completed_count):
        store.update(
            task.id,
            status="done",
            repeat_count=completed_count,
            remind_at=None,
            remind_schedule=[],
        )
        return "completed"

    remind_at, schedule = next_remind_for_task(task, next_due)
    store.update(
        task.id,
        due_at=next_due.isoformat(),
        remind_at=remind_at,
        remind_schedule=schedule,
        repeat_count=completed_count,
        status="pending",
    )
    return "advanced"
