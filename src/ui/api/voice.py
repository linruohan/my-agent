"""语音输入 API。"""

from __future__ import annotations

from typing import Any

from src.ui.api.base import ApiBase


class VoiceApiMixin(ApiBase):
    """语音识别与系统设置。"""

    def get_voice_info(self) -> dict[str, Any]:
        return self._ctrl.get_voice_info()

    def start_voice_input(self) -> dict[str, Any]:
        return self._ctrl.start_voice_input()

    def open_speech_settings(self) -> dict[str, Any]:
        return self._ctrl.open_speech_settings()
