from __future__ import annotations

import sqlite3
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import create_react_agent

from src.infra.config import load_app_config
from src.tools import get_enabled_tools


class AgentGraphBundle:
    """持有 SQLite 连接与编译后的 Agent 图，避免连接被提前关闭。"""

    def __init__(self, graph, conn: sqlite3.Connection, checkpointer: SqliteSaver):
        self.graph = graph
        self._conn = conn
        self.checkpointer = checkpointer

    def close(self) -> None:
        self._conn.close()


def build_agent_graph(llm: BaseChatModel, checkpoint_path: str | Path) -> AgentGraphBundle:
    """构建带 SQLite Checkpoint 的 ReAct Agent 图。"""
    path = Path(checkpoint_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    app_cfg = load_app_config()
    system_prompt = app_cfg.get("agent", {}).get("system_prompt", "").strip()
    tools = get_enabled_tools()
    prompt = system_prompt or "你是一个 helpful 的个人助理。"

    graph = create_react_agent(
        llm,
        tools,
        prompt=prompt,
        checkpointer=checkpointer,
    )
    return AgentGraphBundle(graph, conn, checkpointer)
