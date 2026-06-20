"""LangChain @tool 装饰器：网络搜索工具。"""

from __future__ import annotations

from langchain_core.tools import tool

from src.tools.web.core import SearchEngine, web_search_impl


@tool
def web_search(query: str, engine: SearchEngine = "auto") -> str:
    """搜索网页信息（Bing / 百度）。适用于查询新闻、百科、实时信息等。

    Args:
        query: 搜索关键词或问题
        engine: 搜索引擎 bing / baidu / auto（默认 auto，先 Bing 后百度）
    """
    return web_search_impl(query, engine)


WEB_TOOLS = [web_search]
