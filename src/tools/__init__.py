from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

from src.infra.config import load_tools_config
from src.tools.file.tools import FILE_TOOLS

_TOOLS_DIR = Path(__file__).parent


def _discover_tools() -> list:
    """自动发现所有工具模块中的 *_TOOLS 列表。"""
    all_discovered = []
    for entry in _TOOLS_DIR.iterdir():
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        tools_module = entry / "tools.py"
        if not tools_module.exists():
            continue
        module_name = f"src.tools.{entry.name}.tools"
        try:
            module = importlib.import_module(module_name)
            for attr_name in dir(module):
                if attr_name.endswith("_TOOLS"):
                    tools_list = getattr(module, attr_name)
                    if isinstance(tools_list, list):
                        all_discovered.extend(tools_list)
        except Exception:
            from loguru import logger

            logger.debug("工具模块加载失败: {}", module_name, exc_info=True)
    return all_discovered


_DISCOVERED_TOOLS = _discover_tools()
ALL_TOOLS = FILE_TOOLS + [t for t in _DISCOVERED_TOOLS if t not in FILE_TOOLS]
TOOL_BY_NAME = {t.name: t for t in ALL_TOOLS}

from src.tools.note.tools import add_note
from src.tools.rag.tools import search_notes
from src.tools.task.tools import add_task, complete_task, delete_task, list_tasks, search_tasks
from src.tools.web.tools import web_search
from src.tools.weather.tools import get_weather_forecast
from src.tools.workspace.tools import _CALENDAR_FILE, create_calendar_event, read_calendar


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
# 默认子进程：重 IO / 易阻塞 GIL 的工具。search_notes、天气已同进程（FAISS/HTTP 热路径）。
# find/grep 内部已调 fd/rg 子进程，外层再走 ProcessPool 是双重开销
_DEFAULT_SUBPROCESS_TOOLS = frozenset({
    "web_search",
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
