"""日历冲突检测测试。"""

from __future__ import annotations

from src.tools.workspace.tools import find_calendar_conflicts


def test_find_calendar_conflicts_overlap():
    events = [
        {"title": "站会", "date": "2026-08-01", "time": "09:00", "duration_minutes": 60},
        {"title": "午休", "date": "2026-08-01", "time": "12:00", "duration_minutes": 60},
    ]
    conflicts = find_calendar_conflicts(
        events,
        date="2026-08-01",
        time="09:30",
        duration_minutes=30,
    )
    assert len(conflicts) == 1
    assert conflicts[0]["title"] == "站会"


def test_find_calendar_conflicts_no_overlap():
    events = [
        {"title": "站会", "date": "2026-08-01", "time": "09:00", "duration_minutes": 60},
    ]
    conflicts = find_calendar_conflicts(
        events,
        date="2026-08-01",
        time="10:00",
        duration_minutes=30,
    )
    assert conflicts == []


def test_find_calendar_conflicts_different_day():
    events = [
        {"title": "站会", "date": "2026-08-01", "time": "09:00", "duration_minutes": 60},
    ]
    conflicts = find_calendar_conflicts(
        events,
        date="2026-08-02",
        time="09:00",
        duration_minutes=60,
    )
    assert conflicts == []
