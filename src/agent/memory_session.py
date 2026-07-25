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
        else:
            _states.clear()
