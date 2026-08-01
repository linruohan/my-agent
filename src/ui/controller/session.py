"""多会话管理。"""

from __future__ import annotations

from typing import Any


class SessionMixin:
    """会话 CRUD 与切换。"""

    def new_session(self) -> dict[str, Any]:
        info = self._session_store.create_session("新会话")
        return self._activate_session(info.id, announce=True)

    def list_sessions_api(self) -> dict[str, Any]:
        return {
            "sessions": [
                {"id": s.id, "title": s.title, "active": s.id == self._session_id}
                for s in self._session_store.list_sessions()
            ]
        }

    def switch_session(self, session_id: str) -> dict[str, Any]:
        session_id = str(session_id or "").strip()
        if not session_id:
            return {"ok": False, "error": "会话不存在"}
        if session_id == self._session_id:
            return {"ok": True, "active_id": session_id, **self.list_sessions_api()}
        if not self._session_store.get(session_id):
            return {"ok": False, "error": "会话不存在", **self.list_sessions_api()}
        if self._is_busy():
            return {"ok": False, "error": "请等待当前任务完成"}
        return self._activate_session(session_id, announce=False)

    def delete_session(self, session_id: str) -> dict[str, Any]:
        session_id = str(session_id or "").strip()
        sessions = self._session_store.list_sessions()
        if len(sessions) <= 1:
            return {"ok": False, "error": "至少保留一个会话", **self.list_sessions_api()}

        was_active = session_id == self._session_id
        deleted = self._session_store.delete(session_id) if session_id else False

        # 已删除或不存在：幂等成功，并确保当前会话指针仍有效
        if not deleted:
            return self._ensure_active_session()

        active_missing = was_active or not self._session_store.get(self._session_id)
        if active_missing:
            remaining = self._session_store.list_sessions()
            if remaining:
                return self._activate_session(remaining[0].id, announce=True)
            # 理论上不会走到：前面已保证至少 2 个会话
            created = self._session_store.create_session("新会话")
            return self._activate_session(created.id, announce=True)

        return {"ok": True, **self.list_sessions_api()}

    def rename_session(self, session_id: str, title: str) -> dict[str, Any]:
        session_id = str(session_id or "").strip()
        if not self._session_store.rename(session_id, title):
            return {"ok": False, "error": "重命名失败"}
        return {"ok": True, **self.list_sessions_api()}

    def _ensure_active_session(self) -> dict[str, Any]:
        """当前会话已失效时切换到仍存在的会话，避免前端卡在已删 id。"""
        if self._session_store.get(self._session_id):
            return {"ok": True, "active_id": self._session_id, **self.list_sessions_api()}
        remaining = self._session_store.list_sessions()
        if remaining:
            return self._activate_session(remaining[0].id, announce=True)
        created = self._session_store.create_session("新会话")
        return self._activate_session(created.id, announce=True)

    def _activate_session(self, session_id: str, *, announce: bool) -> dict[str, Any]:
        info = self._session_store.get(session_id)
        if not info:
            return {"ok": False, "error": "会话不存在", **self.list_sessions_api()}
        self._session_id = info.id
        self._thread_id = info.thread_id
        from src.ui.session_history import session_history_limit

        limit = session_history_limit()
        total = self._session_store.count_events(session_id)
        events = self._session_store.load_events(session_id, limit=limit)
        # 只走 load_history（内部会重置前端消息），避免 clear 事件异步晚到把刚加载的历史清空
        self._skip_persist_events = True
        try:
            self.chat.load_history(events)
        finally:
            self._skip_persist_events = False
        if announce and not events:
            self.chat.append_system(f"新会话：{info.title}")
        elif limit and total > len(events):
            self.chat.append_system(f"仅显示最近 {len(events)} 条消息（共 {total} 条）")
        self.chat.set_status(self._status_text("就绪"))
        # 历史已通过 WebChatBridge.load_history 推送，不再回传 events，
        # 避免前端二次 loadHistory + 大 JSON IPC。
        return {
            "ok": True,
            "active_id": session_id,
            "history_via_bridge": True,
            "history_total": total,
            "history_truncated": bool(limit and total > len(events)),
            **self.list_sessions_api(),
        }
