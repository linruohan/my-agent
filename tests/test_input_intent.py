"""input_intent 模块测试。"""

from __future__ import annotations

from src.ui.input_intent import (
    INTENT_LINK,
    INTENT_OCR,
    INTENT_SEARCH,
    INTENT_SLASH_NOTE,
    INTENT_SLASH_OCR,
    extract_link_instruction,
    parse_slash_command,
    resolve_input_intent,
)


def test_parse_slash_note():
    intent = parse_slash_command("/note 添加笔记：hello")
    assert intent is not None
    assert intent.kind == INTENT_SLASH_NOTE
    assert intent.note_content == "hello"


def test_parse_slash_ocr():
    intent = parse_slash_command("/ocr")
    assert intent is not None
    assert intent.kind == INTENT_SLASH_OCR


def test_extract_link_instruction():
    text = "https://example.com/ 获取今日热榜前10条"
    urls = ["https://example.com/"]
    assert extract_link_instruction(text, urls) == "获取今日热榜前10条"


def test_resolve_ocr_with_image_keyword():
    intent = resolve_input_intent("识别文字", [{"type": "image", "path": "a.png"}], llm=None)
    assert intent.kind == INTENT_OCR


def test_resolve_link_with_url_and_text():
    intent = resolve_input_intent(
        "https://www.toutiao.com/ 获取今日热榜前10条",
        [],
        llm=None,
    )
    assert intent.kind == INTENT_LINK
    assert "toutiao.com" in intent.urls[0]


def test_resolve_plain_text_search_fallback():
    intent = resolve_input_intent("今日头条", [], llm=None)
    assert intent.kind == INTENT_SEARCH
    assert intent.search_query == "今日头条"
