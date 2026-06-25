"""LangChain 工具：持久记忆与历史对话检索。"""

from __future__ import annotations

from langchain_core.tools import tool

from src.memory.context_files import (
    memory_file_path,
    read_context_file,
    user_file_path,
    write_context_file,
)
from src.memory.conversation_search import search_past_conversations_merged


@tool
def read_user_profile() -> str:
    """读取 USER.md 中的用户画像（偏好、项目背景等长期信息）。"""
    text = read_context_file(user_file_path(), max_chars=12000)
    return text or "USER.md 为空，尚未记录用户画像。"


@tool
def update_user_profile(content: str, mode: str = "append") -> str:
    """更新 USER.md 用户画像。mode=append 追加，mode=replace 整文件替换。

    Args:
        content: 要写入的 Markdown 内容
        mode: append 或 replace，默认 append
    """
    body = (content or "").strip()
    if not body:
        return "内容为空，未更新 USER.md。"
    write_context_file(user_file_path(), body, mode=mode if mode in ("append", "replace") else "append")
    return f"已{'追加' if mode != 'replace' else '替换'} USER.md（{len(body)} 字符）。"


@tool
def read_agent_memory() -> str:
    """读取 MEMORY.md 中的 Agent 跨会话记忆（经验、重要事实）。"""
    text = read_context_file(memory_file_path(), max_chars=12000)
    return text or "MEMORY.md 为空，尚未积累 Agent 记忆。"


@tool
def update_agent_memory(content: str, mode: str = "append") -> str:
    """更新 MEMORY.md Agent 记忆。学到可复用经验或用户要求记住的信息时使用。

    Args:
        content: 要写入的 Markdown 内容
        mode: append 或 replace，默认 append
    """
    body = (content or "").strip()
    if not body:
        return "内容为空，未更新 MEMORY.md。"
    write_context_file(memory_file_path(), body, mode=mode if mode in ("append", "replace") else "append")
    return f"已{'追加' if mode != 'replace' else '替换'} MEMORY.md（{len(body)} 字符）。"


@tool
def search_past_conversations(keyword: str, limit: int = 10, mode: str = "auto") -> str:
    """搜索历史会话中的用户与助手消息（跨会话）。

    Args:
        keyword: 搜索关键词或自然语言描述
        limit: 最多返回条数，默认 10
        mode: auto（默认，先关键词后语义）| keyword | semantic
    """
    return search_past_conversations_merged(keyword, limit=max(1, min(limit, 30)), mode=mode)


MEMORY_TOOLS = [
    read_user_profile,
    update_user_profile,
    read_agent_memory,
    update_agent_memory,
    search_past_conversations,
]
