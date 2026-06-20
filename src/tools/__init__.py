from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from src.infra.config import load_tools_config
from src.infra.paths import DATA_DIR
from src.memory.rag import search_knowledge_base
from src.tools.file.tools import FILE_TOOLS
from src.tools.search import SearchEngine, web_search_impl
from src.tools.weather import get_weather_forecast_impl

# 工具注册约定：按类别分包（如 file/、web/），各包导出 *_TOOLS 列表，在此汇总。
_TODOS_FILE = DATA_DIR / "workspace" / "todos.json"
_CALENDAR_FILE = DATA_DIR / "workspace" / "calendar.json"
_NOTES_FILE = DATA_DIR / "workspace" / "notes.json"


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
def web_search(query: str, engine: SearchEngine = "auto") -> str:
    """搜索网页信息（Bing / 百度）。适用于查询新闻、百科、实时信息等。

    Args:
        query: 搜索关键词或问题
        engine: 搜索引擎 bing / baidu / auto（默认 auto，先 Bing 后百度）
    """
    return web_search_impl(query, engine)


@tool
def get_weather_forecast(
    city_code: str = "",
    range_type: str = "7d",
    query_text: str = "",
) -> str:
    """查询中国天气网天气预报（当天或 7 天），返回页面 HTML。默认 7 天、使用 config/weather.yaml 地区。

    Args:
        city_code: 可选，中国天气网 9 位城市代码（如 101110101）；留空则用配置
        range_type: 1d（当天）或 7d（7 天），默认 7d
        query_text: 用户原文，用于识别「今天」「7天」等关键词
    """
    return get_weather_forecast_impl(city_code or None, range_type=range_type, query_text=query_text)


@tool
def add_note(content: str, title: str = "") -> str:
    """添加一条个人笔记。

    Args:
        content: 笔记正文
        title: 可选标题，留空则取正文前 30 字
    """
    body = (content or "").strip()
    if not body:
        return "笔记内容不能为空。"
    notes = _load_json(_NOTES_FILE, [])
    note = {
        "id": len(notes) + 1,
        "title": (title or body[:30]).strip() or body[:30],
        "content": body,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    notes.append(note)
    _save_json(_NOTES_FILE, notes)
    return f"已添加笔记 #{note['id']}：{note['title']}"


@tool
def search_notes(query: str) -> str:
    """在个人知识库中检索相关文档片段，用于回答基于用户上传资料的问题。

    Args:
        query: 检索问题或关键词
    """
    return search_knowledge_base(query)


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


OTHER_TOOLS = [
    web_search,
    get_weather_forecast,
    add_note,
    search_notes,
    read_calendar,
    create_calendar_event,
    create_todo,
    list_todos,
]

ALL_TOOLS = FILE_TOOLS + OTHER_TOOLS

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


def requires_confirmation(tool_name: str) -> bool:
    return bool(get_tool_meta(tool_name).get("requires_confirmation"))
