"""兼容层：请使用 src.ui.speech.win。"""
import sys

from src.ui.speech.win import *  # noqa: F403
from src.ui.speech.win import (  # noqa: F401
    SPEECH_PRIVACY_WINERROR,
    _is_speech_privacy_error,
    _join_unique_phrases,
    _privacy_not_ready_result,
    ensure_speech_privacy_ready,
    get_voice_info,
    is_supported,
    open_speech_privacy_settings,
    recognize_once,
)

__all__ = [
    "SPEECH_PRIVACY_WINERROR",
    "_is_speech_privacy_error",
    "_join_unique_phrases",
    "_privacy_not_ready_result",
    "ensure_speech_privacy_ready",
    "get_voice_info",
    "is_supported",
    "open_speech_privacy_settings",
    "recognize_once",
    "sys",
]

sys = sys
