from __future__ import annotations

from src.ui.input_compose import compose_user_message, extract_inline_urls


def test_compose_text_only():
    r = compose_user_message("你好\n\n世界", [])
    assert r["ok"]
    assert "你好" in r["message"]
    assert "世界" in r["message"]


def test_compose_file_attachment():
    r = compose_user_message("请分析", [{"type": "file", "path": r"D:\docs\a.txt", "name": "a.txt"}])
    assert r["ok"]
    assert "a.txt" in r["message"]
    assert r"D:\\docs\\a.txt" in r["message"] or r"D:\docs\a.txt" in r["message"]


def test_compose_empty():
    r = compose_user_message("", [])
    assert not r["ok"]


def test_extract_urls():
    urls = extract_inline_urls("见 https://example.com/foo 和 https://example.com/foo")
    assert urls == ["https://example.com/foo"]
