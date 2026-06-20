from __future__ import annotations

import sqlite3
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import create_react_agent

from src.infra.config import load_app_config
from src.infra.time_context import current_date_context, current_year
from src.tools import get_enabled_tools


class AgentGraphBundle:
    """持有 SQLite 连接与编译后的 Agent 图，避免连接被提前关闭。"""

    def __init__(self, graph, conn: sqlite3.Connection, checkpointer: SqliteSaver):
        self.graph = graph
        self._conn = conn
        self.checkpointer = checkpointer

    def close(self) -> None:
        self._conn.close()


def build_system_prompt(base_prompt: str) -> str:
    """在基础 Prompt 上注入当前日期与搜索行为约束。"""
    date_ctx = current_date_context()
    year = current_year()
    time_block = f"""
【当前时间】今天是 {date_ctx}。当前年份是 {year} 年。所有涉及版本、发布、新闻的判断必须以此为准。

【搜索回答规则】
1. 用户询问时事、软件版本、新特性等时效性内容时，必须先调用 web_search，再基于工具返回的摘要回答。
2. 严禁用训练数据中的旧信息（如「某版本尚未发布」）覆盖搜索结果；若搜索摘要与训练记忆冲突，以搜索结果为准并说明差异。
3. web_search 返回的是内部检索数据，禁止在回复中原文粘贴、逐条复述或展示「【搜索时间】」「【原始查询】」等工具输出格式。
4. 收到 web_search 结果后，必须用自然语言**汇总**成结构化回答：开头直接给出结论，再分点说明要点，附 1–3 个关键来源链接即可。
5. 调用工具前的规划语（如「我需要搜索…」）不要出现在最终回复中；工具执行完毕后只输出面向用户的汇总内容。
6. 若搜索结果明显过时或不足，如实告知用户并建议换个关键词重搜。
"""
    base = base_prompt.strip() or "你是一个 helpful 的个人助理。"
    return base + "\n" + time_block.strip()


def build_agent_graph(llm: BaseChatModel, checkpoint_path: str | Path) -> AgentGraphBundle:
    """构建带 SQLite Checkpoint 与 Human-in-the-loop 的 ReAct Agent 图。"""
    path = Path(checkpoint_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    app_cfg = load_app_config()
    base_prompt = app_cfg.get("agent", {}).get("system_prompt", "").strip()
    tools = get_enabled_tools()
    prompt = build_system_prompt(base_prompt)

    graph = create_react_agent(
        llm,
        tools,
        prompt=prompt,
        checkpointer=checkpointer,
        interrupt_before=["tools"],
    )
    return AgentGraphBundle(graph, conn, checkpointer)
