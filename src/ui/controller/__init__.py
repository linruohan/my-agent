"""AssistantController：组合各功能 Mixin。"""

from __future__ import annotations

from src.ui.controller.agent import AgentMixin
from src.ui.controller.core import CoreMixin
from src.ui.controller.gateway import GatewayMixin
from src.ui.controller.router import RouterMixin
from src.ui.controller.session import SessionMixin
from src.ui.controller.settings import SettingsMixin
from src.ui.controller.turns import TurnsMixin
from src.ui.controller.voice import FilesMixin, VoiceMixin


class AssistantController(
    CoreMixin,
    SettingsMixin,
    SessionMixin,
    RouterMixin,
    TurnsMixin,
    AgentMixin,
    GatewayMixin,
    VoiceMixin,
    FilesMixin,
):
    """Agent 与 Web UI 控制器。"""
