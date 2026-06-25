"""Gateway 通道 chat_id 与本地 Session / Checkpoint thread 映射。"""

from __future__ import annotations

from datetime import datetime, timezone

from src.gateway.inbox import GatewayInbox
from src.ui.session_store import SessionInfo, SessionStore


def gateway_chat_key(source: str, chat_id: str) -> str:
    return f"{source}:{chat_id}"


def resolve_gateway_session(
    inbox: GatewayInbox,
    session_store: SessionStore,
    *,
    source: str,
    chat_id: str,
) -> tuple[str, str]:
    """获取或创建 Gateway 专用会话，返回 (session_id, thread_id)。"""
    key = gateway_chat_key(source, chat_id)
    mapped = inbox.get_chat_session(key)
    if mapped:
        info = session_store.get(mapped)
        if info:
            return info.id, info.thread_id

    title = f"[{source}] {str(chat_id)[:24]}"
    info = session_store.create_session(title)
    inbox.set_chat_session(key, info.id)
    return info.id, info.thread_id
