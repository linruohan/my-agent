"""沙箱内程序化调用 Agent 工具（只读白名单）。"""

from __future__ import annotations

from typing import Any

from src.infra.config import load_app_config

_DEFAULT_ALLOWED = frozenset({
    "list_tasks",
    "search_tasks",
    "read_local_file",
    "list_directory",
    "find_files",
    "grep_files",
    "search_notes",
    "read_user_profile",
    "read_agent_memory",
    "search_past_conversations",
    "list_skills",
    "get_skill_details",
    "list_cron_jobs",
    "web_search",
    "get_weather_forecast",
    "read_calendar",
})


def sandbox_allowed_tools() -> frozenset[str]:
    cfg = load_app_config().get("agent", {}).get("code_sandbox", {}) or {}
    raw = cfg.get("allowed_tools")
    if isinstance(raw, list) and raw:
        return frozenset(str(x) for x in raw)
    return _DEFAULT_ALLOWED


def sandbox_tool_call_enabled() -> bool:
    cfg = load_app_config().get("agent", {}).get("code_sandbox", {}) or {}
    return bool(cfg.get("allow_tool_call", True))


def invoke_sandbox_tool(name: str, args: dict[str, Any] | None = None) -> str:
    from src.tools import TOOL_BY_NAME, get_tool_meta

    tool_name = (name or "").strip()
    if not sandbox_tool_call_enabled():
        return "沙箱内工具调用已禁用。"
    if tool_name not in sandbox_allowed_tools():
        return f"沙箱不允许调用工具：{tool_name}"
    tool = TOOL_BY_NAME.get(tool_name)
    if tool is None:
        return f"未知工具：{tool_name}"
    if bool(get_tool_meta(tool_name).get("requires_confirmation")):
        return f"沙箱不允许调用需确认的工具：{tool_name}"
    try:
        result = tool.invoke(args or {})
        return str(result) if result is not None else ""
    except Exception as exc:
        return f"工具调用失败: {exc}"
