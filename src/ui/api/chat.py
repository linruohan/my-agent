"""聊天与 Agent 控制 API。"""

from __future__ import annotations

from typing import Any

from src.ui.api.base import ApiBase


class ChatApiMixin(ApiBase):
    """消息发送、停止、HITL 审批。"""

    def send_message(self, payload: dict[str, Any] | str) -> bool:
        if isinstance(payload, str):
            payload = {"text": payload, "attachments": []}
        return self._ctrl.send_message(payload)

    def stop_agent(self) -> None:
        self._ctrl.stop_agent()

    def approval_response(self, approved: bool) -> None:
        self._ctrl.approval_response(approved)
