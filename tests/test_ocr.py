from __future__ import annotations

import sys

from src.ui import ocr


def test_paddle_missing_message_on_py314():
    if sys.version_info >= (3, 14):
        assert "3.14" in ocr._paddle_missing_message()


def test_default_engine_is_paddle(monkeypatch):
    monkeypatch.delenv("AGENT_OCR_ENGINE", raising=False)
    assert ocr._ocr_engine_name() == "paddle"
    assert ocr._use_paddle_ocr() is True
    assert ocr._use_winrt_ocr() is False


def test_paddle_ocr_version_defaults_to_v6(monkeypatch):
    monkeypatch.delenv("AGENT_OCR_PADDLE_VERSION", raising=False)
    assert ocr._paddle_ocr_version() == "PP-OCRv6"


def test_paddle_unavailable_without_package(monkeypatch):
    monkeypatch.setattr(ocr.importlib.util, "find_spec", lambda _name: None)
    assert ocr._paddle_available() is False


def test_extract_paddle_text_v3_dict():
    raw = [{"rec_texts": ["你好", "世界"], "rec_scores": [0.9, 0.8]}]
    assert ocr._extract_paddle_text(raw) == ["你好", "世界"]


def test_extract_paddle_text_v2_legacy():
    line = [[[0, 0], [1, 0], [1, 1], [0, 1]], ("测试", 0.95)]
    raw = [[line]]
    assert ocr._extract_paddle_text(raw) == ["测试"]
