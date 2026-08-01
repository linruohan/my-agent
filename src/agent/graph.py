from __future__ import annotations

import sqlite3
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import create_react_agent

from src.agent.history import make_pre_model_hook
from src.agent.hitl import make_hitl_post_model_hook
from src.infra.config import load_app_config
from src.infra.time_context import current_date_context, current_year
from src.agent.memory_session import (
    get_cached_memory_injection,
    get_memory_conversation_state,
    store_memory_injection,
)
from src.memory.context_files import build_memory_prompt_block, build_claude_prompt_block
from src.memory.memory_index import load_all_memory_entries
from src.memory.memory_reader import (
    FindRelevantMemoriesInput,
    build_memory_injection_block,
    find_relevant_memories,
)
from src.memory.rules_loader import build_rules_prompt_block
from src.memory.settings_store import build_critical_rules_prompt_block
from src.tools import get_enabled_tools
from src.tools.process_wrap import wrap_tools_for_process

class AgentGraphBundle:
    """持有 SQLite 连接与编译后的 Agent 图，避免连接被提前关闭。"""

    def __init__(self, graph, conn: sqlite3.Connection, checkpointer: SqliteSaver):
        self.graph = graph
        self._conn = conn
        self.checkpointer = checkpointer

    def close(self) -> None:
        self._conn.close()


def _search_rules_block() -> str:
    date_ctx = current_date_context()
    year = current_year()
    return f"""
【当前时间】今天是 {date_ctx}。当前年份是 {year} 年。所有涉及版本、发布、新闻的判断必须以此为准。

【搜索回答规则】
1. 用户询问时事、软件版本、新特性等时效性内容时，必须先调用 web_search，再基于工具返回的摘要回答。
2. 严禁用训练数据中的旧信息（如「某版本尚未发布」）覆盖搜索结果；若搜索摘要与训练记忆冲突，以搜索结果为准并说明差异。
3. web_search 返回的是内部检索数据，禁止在回复中原文粘贴、逐条复述或展示「【搜索时间】」「【原始查询】」等工具输出格式。
4. 收到 web_search 结果后，必须用自然语言**汇总**成结构化回答：开头直接给出结论，再分点说明要点，附 1–3 个关键来源链接即可。
5. 调用工具前的规划语（如「我需要搜索…」）不要出现在最终回复中；工具执行完毕后只输出面向用户的汇总内容。
6. 若搜索结果明显过时或不足，如实告知用户并建议换个关键词重搜。
""".strip()


def _build_static_prompt(base_prompt: str, current_file: str | None) -> str:
    """构建不含相关记忆检索的静态 prompt 段（文件读取侧已有 mtime 缓存）。"""
    base = base_prompt.strip() or "你是一个 helpful 的个人助理。"
    memory_block = build_memory_prompt_block()
    claude_block = build_claude_prompt_block(current_file=current_file)
    rules_block = build_rules_prompt_block(current_file=current_file)
    critical_block = build_critical_rules_prompt_block()

    parts = [base, _search_rules_block()]
    if critical_block:
        parts.append(f"【强制约束 CRITICAL】\n{critical_block}")
    if claude_block:
        parts.append(f"【项目指导 CLAUDE.md】\n{claude_block}")
    if rules_block:
        parts.append(f"【行为规则 RULES】\n{rules_block}")
    if memory_block:
        parts.append(memory_block)
    return "\n\n".join(parts)


def build_system_prompt(
    base_prompt: str,
    llm: BaseChatModel | None = None,
    state: dict | None = None,
) -> str:
    """在基础 Prompt 上注入当前日期、搜索规则、记忆块与相关记忆。"""
    current_file = state.get("_current_file") if state else None
    parts = [_build_static_prompt(base_prompt, current_file)]

    relevant_memories_block = _build_relevant_memories_block(llm, state)
    if relevant_memories_block:
        parts.append(relevant_memories_block)

    return "\n\n".join(parts)


def _extract_recent_tools(messages: list) -> list[str]:
    """从消息历史中提取最近使用的工具名称。"""
    tools: list[str] = []
    for msg in reversed(messages):
        if len(tools) >= 5:
            break
        if isinstance(msg, dict):
            tool_calls = msg.get("tool_calls", [])
            for call in tool_calls:
                if isinstance(call, dict):
                    tools.append(str(call.get("name", "")))
                elif hasattr(call, "name"):
                    tools.append(str(call.name))
        elif hasattr(msg, "tool_calls") and msg.tool_calls:
            for call in msg.tool_calls:
                if hasattr(call, "name"):
                    tools.append(str(call.name))
    return tools


def _extract_user_query(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            return str(msg.get("content", ""))
        if hasattr(msg, "type") and getattr(msg, "type", None) == "human":
            return str(getattr(msg, "content", "") or "")
        if hasattr(msg, "role") and msg.role == "user":
            return str(msg.content)
    return ""


def _build_relevant_memories_block(
    llm: BaseChatModel | None = None,
    state: dict | None = None,
) -> str:
    """使用小模型选择器构建相关记忆注入块（每用户轮仅检索一次）。"""
    if not llm or not state:
        return ""

    messages = state.get("messages", [])
    if not messages:
        return ""

    user_query = _extract_user_query(messages)
    if not user_query:
        return ""

    cached = get_cached_memory_injection(user_query)
    if cached is not None:
        return cached

    memory_entries = load_all_memory_entries()
    if not memory_entries:
        store_memory_injection(user_query, "")
        return ""

    conversation_state = get_memory_conversation_state()
    already_surfaced = list(conversation_state.already_surfaced_memories)
    recent_tools = _extract_recent_tools(messages)

    input_data = FindRelevantMemoriesInput(
        query=user_query,
        memory_files=memory_entries,
        already_surfaced=already_surfaced,
        recent_tools=recent_tools,
        max_results=5,
    )

    found_memories = find_relevant_memories(llm, input_data)
    if not found_memories:
        store_memory_injection(user_query, "")
        return ""

    conversation_state.add_surfaced([m.file_name for m in found_memories])

    injection = build_memory_injection_block(found_memories)
    block = f"【相关记忆】\n{injection}" if injection else ""
    store_memory_injection(user_query, block)
    return block


def make_dynamic_system_prompt(base_prompt: str, llm: BaseChatModel):
    """每次模型调用前刷新 USER/MEMORY 注入；相关记忆每用户轮仅检索一次。"""

    def prompt_fn(state: dict) -> str:
        return build_system_prompt(base_prompt, llm, state)

    return prompt_fn


def build_agent_graph(llm: BaseChatModel, checkpoint_path: str | Path) -> AgentGraphBundle:
    """构建带 SQLite Checkpoint 与 Human-in-the-loop 的 ReAct Agent 图。"""
    path = Path(checkpoint_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode = WAL")
    checkpointer = SqliteSaver(conn)

    app_cfg = load_app_config()
    agent_cfg = app_cfg.get("agent", {})
    base_prompt = agent_cfg.get("system_prompt", "").strip()
    max_history = int(agent_cfg.get("max_history_messages", 0) or 0)
    max_history_tokens = int(agent_cfg.get("max_history_tokens", 0) or 0)
    tool_result_max_chars = int(agent_cfg.get("tool_result_max_chars", 0) or 0)
    tools = wrap_tools_for_process(get_enabled_tools())
    prompt = make_dynamic_system_prompt(base_prompt, llm)
    pre_model_hook = make_pre_model_hook(
        max_history,
        max_tokens=max_history_tokens,
        tool_result_max_chars=tool_result_max_chars,
    )
    post_model_hook = make_hitl_post_model_hook()

    graph = create_react_agent(
        llm,
        tools,
        prompt=prompt,
        checkpointer=checkpointer,
        pre_model_hook=pre_model_hook,
        post_model_hook=post_model_hook,
    )
    return AgentGraphBundle(graph, conn, checkpointer)
