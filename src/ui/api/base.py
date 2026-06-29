"""AppApi 基类：持有 AssistantController 引用。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.controller import AssistantController


class ApiBase:
    """pywebview API Mixin 基类。"""

    _ctrl: AssistantController
