from __future__ import annotations

from src.ui.link.fetch import _extract_readable_text, _summarize_text, _validate_url


def test_validate_url():
    assert _validate_url("https://example.com") == "https://example.com"


def test_extract_readable_text():
    html = "<html><head><title>T</title></head><body><p>Hello</p></body></html>"
    text = _extract_readable_text(html)
    assert "Hello" in text
    assert "T" in text


def test_summarize_text_truncates():
    long = "a" * 5000
    out = _summarize_text(long, max_chars=100)
    assert len(out) < 5000
    assert "…" in out
