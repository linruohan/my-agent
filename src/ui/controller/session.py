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
        if session_id == self._session_id:
            return {"ok": True, **self.list_sessions_api()}
        if not self._session_store.get(session_id):
            return {"ok": False, "error": "会话不存在"}
        if self._is_busy():
            return {"ok": False, "error": "请等待当前任务完成"}
        return self._activate_session(session_id, announce=False)

    def delete_session(self, session_id: str) -> dict[str, Any]:
        sessions = self._session_store.list_sessions()
        if len(sessions) <= 1:
            return {"ok": False, "error": "至少保留一个会话"}
        if not self._session_store.delete(session_id):
            return {"ok": False, "error": "会话不存在"}
        if session_id == self._session_id:
            remaining = self._session_store.list_sessions()
            if remaining:
                return self._activate_session(remaining[0].id, announce=True)
        return {"ok": True, **self.list_sessions_api()}

    def rename_session(self, session_id: str, title: str) -> dict[str, Any]:
        if not self._session_store.rename(session_id, title):
            return {"ok": False, "error": "重命名失败"}
        return {"ok": True, **self.list_sessions_api()}

    def _activate_session(self, session_id: str, *, announce: bool) -> dict[str, Any]:
        info = self._session_store.get(session_id)
        if not info:
            return {"ok": False, "error": "会话不存在"}
        self._session_id = info.id
        self._thread_id = info.thread_id
        self.chat.clear()
        events = self._session_store.load_events(session_id)
        self._skip_persist_events = True
        try:
            if events:
                self.chat.load_history(events)
        finally:
            self._skip_persist_events = False
        if announce and not events:
            self.chat.append_system(f"新会话：{info.title}")
        self.chat.set_status(self._status_text("就绪"))
        return {
            "ok": True,
            "active_id": session_id,
            "events": events,
            **self.list_sessions_api(),
        }
