"""LangChain @tool 装饰器：个人笔记工具。"""

from __future__ import annotations

from langchain_core.tools import tool

from src.tools.note.store import NoteStore


@tool
def add_note(content: str, title: str = "") -> str:
    """添加一条个人笔记（note.db）。

    Args:
        content: 笔记正文
        title: 可选标题，留空则取正文前 30 字
    """
    body = (content or "").strip()
    if not body:
        return "笔记内容不能为空。"
    row = NoteStore().add(title, body)
    return f"已添加笔记 #{row.id}：{row.title}"


NOTE_TOOLS = [add_note]
