"""LangChain 工具：沙箱代码执行。"""

from __future__ import annotations

from langchain_core.tools import tool

from src.tools.code.sandbox import execute_code_in_sandbox, reset_code_session


@tool
def execute_code(code: str, session_id: str = "default") -> str:
    """在持久化 Python 沙箱中执行代码。同 session_id 下变量跨调用保留。

    沙箱限制：禁止 os/subprocess/socket 等危险 import；默认 30s 超时。
    沙箱内可调用 call_tool("工具名", key=value) 使用只读 Agent 工具（如 list_tasks、read_local_file）。
    适合数据分析、批量文本处理、多步脚本。

    Args:
        code: Python 代码
        session_id: 会话 ID，默认 default；不同任务可用不同 ID 隔离状态
    """
    return execute_code_in_sandbox(code, session_id=session_id or "default")


@tool
def reset_code_session_tool(session_id: str = "default") -> str:
    """清空代码沙箱会话状态（变量与定义）。

    Args:
        session_id: 要重置的会话 ID
    """
    reset_code_session(session_id or "default")
    return f"已重置代码沙箱会话「{session_id or 'default'}」。"


CODE_TOOLS = [execute_code, reset_code_session_tool]
