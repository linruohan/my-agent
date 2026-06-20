from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import tool

from src.infra.config import load_tools_config
from src.infra.paths import DATA_DIR
from src.memory.rag import search_knowledge_base
from src.tools.files import (
    find_files_impl,
    grep_files_impl,
    list_directory_impl,
    read_local_file_impl,
)
from src.tools.search import SearchEngine, web_search_impl

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
def search_tools_status() -> str:
    """查看本地文件搜索 CLI 工具（fd、ripgrep）的安装状态，并给出安装建议。"""
    return cli_tools_status_text()


@tool
def find_files(
    pattern: str,
    root: str = "",
    file_type: str = "any",
    max_results: int = 50,
) -> str:
    """按文件名或通配符查找本地文件/文件夹（类似 Everything / fd）。

    Args:
        pattern: 文件名模式，支持通配符如 *.py、*config*、README.md
        root: 搜索根目录，留空则使用默认允许目录（用户主目录等）
        file_type: any（默认）/ file / dir
        max_results: 最大返回条数，默认 50
    """
    return find_files_impl(pattern, root, file_type, max_results)


@tool
def grep_files(
    pattern: str,
    root: str = "",
    glob: str = "*",
    max_results: int = 30,
    context_lines: int = 2,
) -> str:
    """在本地文件内容中搜索文本或正则表达式（类似 ripgrep / grep）。

    Args:
        pattern: 搜索词或正则表达式
        root: 搜索根目录，留空则使用默认允许目录
        glob: 文件名过滤，如 *.py、*.txt，默认 * 表示所有文本类文件
        max_results: 最大匹配条数
        context_lines: 匹配行前后显示的上下文行数
    """
    return grep_files_impl(pattern, root, glob, max_results, context_lines)


@tool
def list_directory(path: str = "", max_entries: int = 100) -> str:
    """列出本地目录下的文件和子文件夹。

    Args:
        path: 目录路径，留空则列出默认根目录
        max_entries: 最大显示条目数
    """
    return list_directory_impl(path, max_entries)


@tool
def read_local_file(path: str, max_lines: int = 200, offset: int = 1) -> str:
    """读取本地文本文件的内容（需在允许目录范围内）。

    Args:
        path: 文件绝对或相对路径
        max_lines: 最多读取行数，默认 200
        offset: 起始行号（从 1 开始）
    """
    return read_local_file_impl(path, max_lines, offset)


@tool
def web_search(query: str, engine: SearchEngine = "auto") -> str:
    """搜索网页信息（Bing / 百度）。适用于查询新闻、百科、实时信息等。

    Args:
        query: 搜索关键词或问题
        engine: 搜索引擎 bing / baidu / auto（默认 auto，先 Bing 后百度）
    """
    return web_search_impl(query, engine)


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


ALL_TOOLS = [
    search_tools_status,
    find_files,
    grep_files,
    list_directory,
    read_local_file,
    web_search,
    search_notes,
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


def requires_confirmation(tool_name: str) -> bool:
    return bool(get_tool_meta(tool_name).get("requires_confirmation"))
