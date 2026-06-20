"""语音识别（Windows SAPI / WinRT）。"""

from src.ui.speech.win import (
    SPEECH_PRIVACY_HINT,
    SPEECH_PRIVACY_WINERROR,
    ensure_speech_privacy_ready,
    get_voice_info,
    is_supported,
    open_speech_privacy_settings,
    recognize_once,
)

__all__ = [
    "SPEECH_PRIVACY_HINT",
    "SPEECH_PRIVACY_WINERROR",
    "ensure_speech_privacy_ready",
    "get_voice_info",
    "is_supported",
    "open_speech_privacy_settings",
    "recognize_once",
]
