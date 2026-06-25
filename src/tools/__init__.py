from __future__ import annotations

from typing import Any

from src.infra.config import load_tools_config
from src.tools.automation.tools import AUTOMATION_TOOLS
from src.tools.browser.tools import BROWSER_TOOLS
from src.tools.code.tools import CODE_TOOLS
from src.tools.file.tools import FILE_TOOLS
from src.tools.memory.tools import MEMORY_TOOLS
from src.tools.note.tools import NOTE_TOOLS, add_note
from src.tools.rag.tools import RAG_TOOLS, search_notes
from src.tools.skill.tools import SKILL_TOOLS
from src.tools.task.tools import TASK_TOOLS, add_task, complete_task, delete_task, list_tasks, search_tasks
from src.tools.web.tools import WEB_TOOLS, web_search
from src.tools.weather.tools import WEATHER_TOOLS, get_weather_forecast
from src.tools.workspace.tools import (
    WORKSPACE_TOOLS,
    _CALENDAR_FILE,
    create_calendar_event,
    read_calendar,
)

# 工具注册约定：按类别分包，各包导出 *_TOOLS 列表，在此汇总。
OTHER_TOOLS = (
    WEB_TOOLS
    + BROWSER_TOOLS
    + WEATHER_TOOLS
    + NOTE_TOOLS
    + TASK_TOOLS
    + RAG_TOOLS
    + WORKSPACE_TOOLS
    + MEMORY_TOOLS
    + SKILL_TOOLS
    + CODE_TOOLS
    + AUTOMATION_TOOLS
)

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


# 默认走子进程：网络 I/O、大规模文件搜索、向量检索等可能阻塞 GIL 的工具
_DEFAULT_SUBPROCESS_TOOLS = frozenset({
    "web_search",
    "search_notes",
    "find_files",
    "grep_files",
    "get_weather_forecast",
})


def should_run_in_process(tool_name: str) -> bool:
    """是否将工具包装为子进程执行。tools.yaml 可用 run_in_process 覆盖。"""
    from src.tools.tool_worker import tool_process_enabled

    if not tool_process_enabled():
        return False
    meta = get_tool_meta(tool_name)
    if "run_in_process" in meta:
        return bool(meta["run_in_process"])
    return tool_name in _DEFAULT_SUBPROCESS_TOOLS
