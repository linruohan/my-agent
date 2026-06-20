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
