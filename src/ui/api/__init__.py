"""pywebview js_api：按功能 Mixin 组合。"""

from __future__ import annotations

from src.ui.api.chat import ChatApiMixin
from src.ui.api.input import InputApiMixin
from src.ui.api.session import SessionApiMixin
from src.ui.api.settings import SettingsApiMixin
from src.ui.api.system import SystemApiMixin
from src.ui.api.voice import VoiceApiMixin
from src.ui.controller import AssistantController


class AppApi(
    SessionApiMixin,
    SettingsApiMixin,
    ChatApiMixin,
    InputApiMixin,
    VoiceApiMixin,
    SystemApiMixin,
):
    """pywebview js_api 桥接层。"""

    def __init__(self, controller: AssistantController) -> None:
        self._ctrl = controller
