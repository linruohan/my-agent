from __future__ import annotations

from pathlib import Path

from src.ui.input_compose import (
    build_image_previews,
    compose_user_message,
    extract_inline_urls,
    format_ocr_reply,
    has_sendable_content,
    image_to_data_url,
    is_ocr_only_request,
)


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


def test_image_to_data_url(tmp_path: Path):
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    result = image_to_data_url(img)
    assert result["ok"]
    assert result["data_url"].startswith("data:image/png;base64,")


def test_build_image_previews(tmp_path: Path):
    img = tmp_path / "shot.jpg"
    img.write_bytes(b"\xff\xd8\xff")
    previews = build_image_previews([{"type": "image", "path": str(img), "name": "shot.jpg"}])
    assert len(previews) == 1
    assert previews[0]["name"] == "shot.jpg"
    assert previews[0]["data_url"].startswith("data:")


def test_has_sendable_content():
    assert has_sendable_content("", [{"type": "image", "path": "a.png"}])
    assert has_sendable_content("hi", [])
    assert not has_sendable_content("", [])


def test_is_ocr_only_request():
    imgs = [{"type": "image", "path": "a.png"}]
    assert is_ocr_only_request("", imgs)
    assert is_ocr_only_request("识别文本", imgs)
    assert is_ocr_only_request("OCR", imgs)
    assert not is_ocr_only_request("请总结图片内容", imgs)
    assert not is_ocr_only_request("", [{"type": "file", "path": "a.txt"}])


def test_format_ocr_reply():
    assert format_ocr_reply([{"name": "a.png", "text": "你好"}]) == "你好"
    reply = format_ocr_reply(
        [
            {"name": "a.png", "text": "A"},
            {"name": "b.png", "text": "B"},
        ]
    )
    assert "**a.png**" in reply
    assert "A" in reply and "B" in reply
