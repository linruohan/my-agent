from __future__ import annotations

import sys

from src.ui import speech_win


def test_is_supported_on_win32():
    if sys.platform == "win32":
        # 依赖已安装时应为 True
        assert isinstance(speech_win.is_supported(), bool)


def test_recognize_once_non_windows(monkeypatch):
    monkeypatch.setattr(speech_win.sys, "platform", "linux")
    r = speech_win.recognize_once()
    assert r["ok"] is False


def test_join_unique_phrases_dedupes():
    assert speech_win._join_unique_phrases(["python314", "python314"]) == "python314"
    assert speech_win._join_unique_phrases(["hello", "hello world"]) == "hello world"
    assert speech_win._join_unique_phrases(["a", "b", "b"]) == "a b"


def test_is_speech_privacy_error():
    err = OSError(None, "The speech privacy policy was not accepted", None, speech_win.SPEECH_PRIVACY_WINERROR)
    assert speech_win._is_speech_privacy_error(err) is True
    assert speech_win._is_speech_privacy_error(OSError("other")) is False


def test_privacy_not_ready_result():
    r = speech_win._privacy_not_ready_result(settings_opened=True)
    assert r["ok"] is False
    assert r["needs_speech_settings"] is True
    assert r["settings_opened"] is True
    assert "在线语音识别" in r["error"]


def test_ensure_speech_privacy_skipped_for_local(monkeypatch):
    monkeypatch.delenv("AGENT_VOICE_ENGINE", raising=False)
    assert speech_win.ensure_speech_privacy_ready() is None
