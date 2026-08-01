"""会话级记忆露脸状态（跨 prompt 调用持久，不依赖 LangGraph messages-only state）。"""

from __future__ import annotations

import contextvars
import threading

from src.memory.memory_reader import ConversationState

_current_thread_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "memory_thread_id",
    default=None,
)
_lock = threading.Lock()
_states: dict[str, ConversationState] = {}
# 同一用户轮次内只做一次相关记忆检索（thread_id -> 已检索的 user_query）
_memory_retrieved_for: dict[str, str] = {}
# 同一用户轮次内缓存已注入的相关记忆块
_memory_injection_cache: dict[str, str] = {}


def set_memory_thread_id(thread_id: str | None) -> contextvars.Token:
    return _current_thread_id.set(thread_id)


def reset_memory_thread_id(token: contextvars.Token) -> None:
    _current_thread_id.reset(token)


def get_memory_conversation_state() -> ConversationState:
    thread_id = _current_thread_id.get()
    if not thread_id:
        return ConversationState()
    with _lock:
        state = _states.get(thread_id)
        if state is None:
            state = ConversationState()
            _states[thread_id] = state
        return state


def clear_memory_conversation_state(thread_id: str | None = None) -> None:
    with _lock:
        if thread_id:
            _states.pop(thread_id, None)
            _memory_retrieved_for.pop(thread_id, None)
            _memory_injection_cache.pop(thread_id, None)
        else:
            _states.clear()
            _memory_retrieved_for.clear()
            _memory_injection_cache.clear()


def begin_memory_turn(thread_id: str | None = None) -> None:
    """新用户回合开始时清除本轮记忆检索标记。"""
    tid = thread_id or _current_thread_id.get()
    if not tid:
        return
    with _lock:
        _memory_retrieved_for.pop(tid, None)
        _memory_injection_cache.pop(tid, None)


def get_cached_memory_injection(user_query: str) -> str | None:
    """若本轮已为同一用户查询检索过记忆，返回缓存注入块（可能为空串）。"""
    thread_id = _current_thread_id.get()
    if not thread_id:
        return None
    with _lock:
        if _memory_retrieved_for.get(thread_id) != user_query:
            return None
        return _memory_injection_cache.get(thread_id, "")


def store_memory_injection(user_query: str, block: str) -> None:
    thread_id = _current_thread_id.get()
    if not thread_id:
        return
    with _lock:
        _memory_retrieved_for[thread_id] = user_query
        _memory_injection_cache[thread_id] = block
