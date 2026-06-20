"""LangChain @tool 装饰器：知识库检索。"""

from __future__ import annotations

from langchain_core.tools import tool

from src.memory.rag import search_knowledge_base


@tool
def search_notes(query: str) -> str:
    """在个人知识库中检索相关文档片段，用于回答基于用户上传资料的问题。

    Args:
        query: 检索问题或关键词
    """
    return search_knowledge_base(query)


RAG_TOOLS = [search_notes]
