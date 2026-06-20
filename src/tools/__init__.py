from __future__ import annotations

from typing import Any

from src.infra.config import load_tools_config
from src.tools.file.tools import FILE_TOOLS
from src.tools.note.tools import NOTE_TOOLS, add_note
from src.tools.rag.tools import RAG_TOOLS, search_notes
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
OTHER_TOOLS = WEB_TOOLS + WEATHER_TOOLS + NOTE_TOOLS + TASK_TOOLS + RAG_TOOLS + WORKSPACE_TOOLS

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
