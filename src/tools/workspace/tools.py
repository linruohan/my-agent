"""LangChain @tool 装饰器：日历（JSON 工作区）。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from src.infra.paths import DATA_DIR

_CALENDAR_FILE = DATA_DIR / "workspace" / "calendar.json"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _event_range(date: str, time: str, duration_minutes: int) -> tuple[datetime, datetime]:
    start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end = start + timedelta(minutes=max(1, int(duration_minutes or 60)))
    return start, end


def find_calendar_conflicts(
    events: list[dict[str, Any]],
    *,
    date: str,
    time: str,
    duration_minutes: int,
) -> list[dict[str, Any]]:
    """找出与拟创建事件时间重叠的已有日程。"""
    try:
        new_start, new_end = _event_range(date, time, duration_minutes)
    except ValueError:
        return []

    conflicts: list[dict[str, Any]] = []
    for event in events:
        if str(event.get("date") or "") != date:
            continue
        try:
            existing_start, existing_end = _event_range(
                str(event.get("date")),
                str(event.get("time") or "09:00"),
                int(event.get("duration_minutes") or 60),
            )
        except (TypeError, ValueError):
            continue
        if new_start < existing_end and existing_start < new_end:
            conflicts.append(event)
    return conflicts


@tool
def read_calendar(date: str = "") -> str:
    """读取指定日期的日程安排。

    Args:
        date: 日期，格式 YYYY-MM-DD；留空则读取今天
    """
    target = date or datetime.now().strftime("%Y-%m-%d")
    events = _load_json(_CALENDAR_FILE, [])
    day_events = [e for e in events if e.get("date") == target]
    if not day_events:
        return f"{target} 暂无日程安排。"
    lines = [f"- {e['time']} {e['title']}" for e in day_events]
    return f"{target} 的日程：\n" + "\n".join(lines)


@tool
def create_calendar_event(
    title: str,
    date: str,
    time: str = "09:00",
    duration_minutes: int = 60,
) -> str:
    """在日历中创建新事件。敏感操作，执行前需用户确认。创建前会检测时间冲突。

    Args:
        title: 事件标题
        date: 日期 YYYY-MM-DD
        time: 开始时间 HH:MM
        duration_minutes: 持续时间（分钟）
    """
    try:
        _event_range(date, time, duration_minutes)
    except ValueError:
        return "日期或时间格式无效，请使用 YYYY-MM-DD 与 HH:MM。"

    events = _load_json(_CALENDAR_FILE, [])
    conflicts = find_calendar_conflicts(
        events,
        date=date,
        time=time,
        duration_minutes=duration_minutes,
    )
    event = {
        "id": len(events) + 1,
        "title": title,
        "date": date,
        "time": time,
        "duration_minutes": duration_minutes,
    }
    events.append(event)
    _save_json(_CALENDAR_FILE, events)

    msg = f"已创建日程：{date} {time} - {title}"
    if conflicts:
        lines = [
            f"- {c.get('time')} {c.get('title')}（{c.get('duration_minutes', 60)} 分钟）"
            for c in conflicts
        ]
        msg += "\n⚠️ 与以下日程时间冲突：\n" + "\n".join(lines)
    return msg


WORKSPACE_TOOLS = [
    read_calendar,
    create_calendar_event,
]
