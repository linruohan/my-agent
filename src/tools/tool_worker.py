"""Agent 工具在独立子进程中执行。"""

from __future__ import annotations

import json
import os
import traceback
from typing import Any

from loguru import logger

from src.infra.process_executor import run_in_process
from src.infra.timing import log_timing


def tool_process_enabled() -> bool:
    return os.environ.get("AGENT_TOOL_IN_PROCESS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _default_tool_timeout() -> float:
    raw = os.environ.get("AGENT_TOOL_PROCESS_TIMEOUT", "300")
    try:
        return float(raw)
    except ValueError:
        return 300.0


def _tool_invoke_worker(tool_name: str, args: dict[str, Any]) -> str:
    from src.tools import TOOL_BY_NAME

    tool = TOOL_BY_NAME.get(tool_name)
    if tool is None:
        error_info = {
            "success": False,
            "error_type": "ToolNotFound",
            "error_message": f"未知工具: {tool_name}",
            "traceback": "",
        }
        return json.dumps(error_info, ensure_ascii=False)

    try:
        result = tool.invoke(args)
        success_info = {
            "success": True,
            "result": str(result) if result is not None else "",
        }
        return json.dumps(success_info, ensure_ascii=False)
    except Exception as exc:
        logger.exception("[tool-worker] {} 执行失败", tool_name)
        error_info = {
            "success": False,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "traceback": traceback.format_exc()[:2000],
        }
        return json.dumps(error_info, ensure_ascii=False)


def invoke_tool_in_process(
    tool_name: str,
    args: dict[str, Any] | None = None,
    *,
    timeout: float | None = None,
) -> str:
    if not tool_process_enabled():
        from src.tools import TOOL_BY_NAME

        tool = TOOL_BY_NAME[tool_name]
        with log_timing("tool", name=tool_name, process="inline"):
            try:
                result = tool.invoke(args or {})
                return str(result) if result is not None else ""
            except Exception as exc:
                logger.exception("[tool-worker] {} 执行失败", tool_name)
                return f"工具执行失败: {exc}"

    with log_timing("tool", name=tool_name, process="subprocess"):
        raw_result = run_in_process(
            _tool_invoke_worker,
            tool_name,
            args or {},
            pool="tools",
            timeout=timeout if timeout is not None else _default_tool_timeout(),
        )
        try:
            parsed = json.loads(raw_result)
            if parsed.get("success"):
                return parsed.get("result", "")
            error_type = parsed.get("error_type", "Unknown")
            error_msg = parsed.get("error_message", "")
            logger.warning("[tool-worker] {} 执行失败: {} - {}", tool_name, error_type, error_msg)
            return f"工具执行失败 [{error_type}]: {error_msg}"
        except json.JSONDecodeError:
            return raw_result
