"""重复任务调度与提醒测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch


import pytest

from src.tools.task.repeat import (
    add_interval,
    advance_repeat_task,
    decode_repeat_rule,
    should_complete_repeat,
)
from src.tools.task.scheduler import TaskReminderService
from src.tools.task.store import TaskStore

TZ = timezone(timedelta(hours=8))
REF = datetime(2026, 6, 21, 10, 0, tzinfo=TZ)


def test_decode_repeat_rule():
    rule = decode_repeat_rule('{"every": 2, "unit": "day", "times": 3}')
    assert rule == {"every": 2, "unit": "day", "times": 3}


def test_add_interval_day():
    nxt = add_interval(REF, 1, "day")
    assert nxt.day == 22


def test_add_interval_month():
    base = datetime(2026, 1, 31, 9, 0, tzinfo=TZ)
    nxt = add_interval(base, 1, "month")
    assert nxt.month == 2 and nxt.day == 28


def test_should_complete_by_count():
    from src.tools.task.store import TaskRow

    row = TaskRow(
        id=1,
        title="t",
        content="",
        due_at=REF.isoformat(),
        repeat_rule='{"every": 1, "unit": "day", "times": 2}',
        remind_at=None,
        created_at=REF.isoformat(),
        updated_at=REF.isoformat(),
        repeat_end="2",
        repeat_count=1,
    )
    next_due = add_interval(REF, 1, "day")
    assert should_complete_repeat(row, next_due=next_due, completed_count=2) is True
    assert should_complete_repeat(row, next_due=next_due, completed_count=1) is False


def test_advance_repeat_task(tmp_path: Path):
    store = TaskStore(tmp_path / "task.db")
    due = REF.isoformat()
    row = store.add(
        "每日站会",
        "",
        due_at=due,
        repeat_rule='{"every": 1, "unit": "day", "times": 5}',
        repeat_end="none",
        remind_spec="1h",
    )
    remind_before = datetime.fromisoformat(row.remind_at)
    assert remind_before.hour == 9

    outcome = advance_repeat_task(store, row, now=REF + timedelta(hours=10))
    assert outcome == "advanced"
    updated = store.get(row.id)
    assert updated is not None
    assert updated.repeat_count == 1
    assert updated.due_at is not None
    assert datetime.fromisoformat(updated.due_at).day == 22
    assert updated.remind_at is not None


def test_advance_repeat_completes_at_limit(tmp_path: Path):
    store = TaskStore(tmp_path / "task.db")
    row = store.add(
        "两次任务",
        "",
        due_at=REF.isoformat(),
        repeat_rule='{"every": 1, "unit": "day", "times": 2}',
        repeat_end="2",
    )
    store.update(row.id, repeat_count=1)
    row = store.get(row.id)
    assert row is not None

    outcome = advance_repeat_task(store, row, now=REF)
    assert outcome == "completed"
    done = store.get(row.id)
    assert done is not None
    assert done.status == "done"
    assert done.repeat_count == 2


def test_scheduler_reminder_and_due(tmp_path: Path):
    store = TaskStore(tmp_path / "task.db")
    past = (REF - timedelta(minutes=5)).isoformat()
    row = store.add("提醒任务", "内容", due_at=past, remind_at=past)

    svc = TaskReminderService(store, interval_sec=999)
    with patch("src.tools.task.scheduler.notify_task", return_value=True) as toast:
        svc.tick(now=REF)
        assert toast.call_count >= 2
        updated = store.get(row.id)
        assert updated is not None
        assert updated.remind_at is None
        assert updated.status == "expired"


def test_scheduler_advances_repeat(tmp_path: Path):
    store = TaskStore(tmp_path / "task.db")
    past = (REF - timedelta(minutes=1)).isoformat()
    row = store.add(
        "重复",
        "",
        due_at=past,
        repeat_rule='{"every": 1, "unit": "day", "times": 9}',
        repeat_end="none",
    )
    svc = TaskReminderService(store)
    with patch("src.tools.task.scheduler.notify_task", return_value=True):
        svc.tick(now=REF)
    updated = store.get(row.id)
    assert updated is not None
    assert updated.repeat_count == 1
    assert updated.status == "pending"
    assert datetime.fromisoformat(updated.due_at).day == 22


def test_notify_win11toast(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_notify(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setitem(__import__("sys").modules, "win11toast", type("M", (), {"notify": staticmethod(fake_notify)}))
    from src.tools.task.notify import build_task_toast_xml, send_task_toast

    monkeypatch.setattr("src.tools.task.notify.sys.platform", "win32")
    assert send_task_toast(
        "写报告",
        "整理素材",
        owner="林若寒",
        due_at="2026-06-21T17:30:00+08:00",
        kind="reminder",
    ) is True
    assert "xml" in captured
    xml = captured["xml"]
    assert "任务名" in xml and "写报告" in xml
    assert "负责人" in xml and "林若寒" in xml
    assert "截止时间" in xml
    assert 'scenario="reminder"' in xml


def test_build_task_toast_xml_due_kind():
    from src.tools.task.notify import build_task_toast_xml

    xml = build_task_toast_xml(
        task_title="部署上线",
        owner="张三",
        due_at="2026-06-21T17:30:00+08:00",
        kind="due",
    )
    assert 'scenario="alarm"' in xml
    assert "任务到期" in xml
    assert "部署上线" in xml
