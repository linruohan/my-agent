"""将 LangChain 工具包装为子进程执行（仅重工具）。"""

from __future__ import annotations

from langchain_core.tools import BaseTool, StructuredTool

from src.tools import should_run_in_process, tool_worker


def wrap_tools_for_process(tools: list[BaseTool]) -> list[BaseTool]:
    if not tool_worker.tool_process_enabled():
        return tools
    return [_wrap_tool(tool) if should_run_in_process(tool.name) else tool for tool in tools]


def _wrap_tool(tool: BaseTool) -> BaseTool:
    name = tool.name
    description = tool.description or ""

    def _invoke(**kwargs: object) -> str:
        return tool_worker.invoke_tool_in_process(name, dict(kwargs))

    kwargs: dict = {
        "name": name,
        "description": description,
        "func": _invoke,
    }
    if getattr(tool, "args_schema", None) is not None:
        kwargs["args_schema"] = tool.args_schema
    return StructuredTool.from_function(**kwargs)
