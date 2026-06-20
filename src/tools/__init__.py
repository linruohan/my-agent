from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from src.infra.config import load_tools_config
from src.infra.paths import DATA_DIR

_TODOS_FILE = DATA_DIR / "workspace" / "todos.json"
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


@tool
def web_search(query: str) -> str:
    """搜索网页信息。适用于查询新闻、天气、百科等实时或通用信息。

    Args:
        query: 搜索关键词或问题
    """
    # MVP 占位实现；Phase 2 可接入 Tavily / DuckDuckGo
    return (
        f"[搜索占位] 关于「{query}」的模拟结果："
        "请配置真实搜索 API 或在 Phase 2 接入 langchain-community 搜索工具。"
    )


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
    """在日历中创建新事件。敏感操作，执行前需用户确认。

    Args:
        title: 事件标题
        date: 日期 YYYY-MM-DD
        time: 开始时间 HH:MM
        duration_minutes: 持续时间（分钟）
    """
    events = _load_json(_CALENDAR_FILE, [])
    event = {
        "id": len(events) + 1,
        "title": title,
        "date": date,
        "time": time,
        "duration_minutes": duration_minutes,
    }
    events.append(event)
    _save_json(_CALENDAR_FILE, events)
    return f"已创建日程：{date} {time} - {title}"


@tool
def create_todo(title: str, due_date: str = "", priority: str = "normal") -> str:
    """创建一条待办事项。

    Args:
        title: 待办标题
        due_date: 截止日期 ISO 格式，如 2026-06-20，可留空
        priority: 优先级 low / normal / high
    """
    todos = _load_json(_TODOS_FILE, [])
    todo = {
        "id": len(todos) + 1,
        "title": title,
        "due_date": due_date or None,
        "priority": priority,
        "done": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    todos.append(todo)
    _save_json(_TODOS_FILE, todos)
    return f"已创建待办 #{todo['id']}：{title}（优先级: {priority}）"


@tool
def list_todos(include_done: bool = False) -> str:
    """列出所有待办事项。

    Args:
        include_done: 是否包含已完成项
    """
    todos = _load_json(_TODOS_FILE, [])
    filtered = todos if include_done else [t for t in todos if not t.get("done")]
    if not filtered:
        return "当前没有待办事项。"
    lines = []
    for t in filtered:
        due = f"，截止 {t['due_date']}" if t.get("due_date") else ""
        lines.append(f"#{t['id']} [{t.get('priority', 'normal')}] {t['title']}{due}")
    return "待办列表：\n" + "\n".join(lines)


ALL_TOOLS = [
    web_search,
    read_calendar,
    create_calendar_event,
    create_todo,
    list_todos,
]

TOOL_BY_NAME = {t.name: t for t in ALL_TOOLS}


def get_enabled_tools() -> list:
    cfg = load_tools_config().get("tools", {})
    enabled = []
    for tool_obj in ALL_TOOLS:
        meta = cfg.get(tool_obj.name, {})
        if meta.get("enabled", True):
            enabled.append(tool_obj)
    return enabled


def get_tool_meta(name: str) -> dict[str, Any]:
    cfg = load_tools_config().get("tools", {})
    return cfg.get(name, {"risk": "low", "requires_confirmation": False})
