"""会话管理 API。"""

from __future__ import annotations

from typing import Any

from src.ui.api.base import ApiBase


class SessionApiMixin(ApiBase):
    """多会话 CRUD。"""

    def get_initial_state(self) -> dict[str, Any]:
        return self._ctrl.build_initial_state()

    def new_session(self) -> dict[str, Any]:
        return self._ctrl.new_session()

    def list_sessions(self) -> dict[str, Any]:
        return self._ctrl.list_sessions_api()

    def switch_session(self, session_id: str) -> dict[str, Any]:
        return self._ctrl.switch_session(session_id)

    def delete_session(self, session_id: str) -> dict[str, Any]:
        return self._ctrl.delete_session(session_id)

    def rename_session(self, session_id: str, title: str) -> dict[str, Any]:
        return self._ctrl.rename_session(session_id, title)

    def load_earlier_events(
        self,
        session_id: str,
        before_seq: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return self._ctrl.load_earlier_events(session_id, before_seq, limit)
