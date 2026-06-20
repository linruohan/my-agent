"""search_turn 模块测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.ui.search_turn import search_result_ok


def test_search_result_ok():
    assert search_result_ok("1. 标题\n摘要") is True
    assert search_result_ok("搜索失败: timeout") is False
    assert search_result_ok("未找到相关结果") is False
    assert search_result_ok("") is False


def test_run_web_search_turn_streams_tokens(monkeypatch):
    from src.ui import search_turn

    monkeypatch.setattr(
        search_turn,
        "invoke_tool_in_process",
        lambda name, args: "1. 示例\n摘要内容",
    )

    llm = MagicMock()

    class Chunk:
        def __init__(self, content: str):
            self.content = content

    llm.stream.return_value = [Chunk("你好"), Chunk("世界")]

    tokens: list[str] = []
    statuses: list[tuple[str, str | None]] = []

    response, raw, ok = search_turn.run_web_search_turn(
        llm,
        "今日头条",
        on_token=tokens.append,
        on_search_status=lambda t, a: statuses.append((t, a)),
    )

    assert ok is True
    assert raw.startswith("1.")
    assert response == "你好世界"
    assert tokens == ["你好", "世界"]
    assert statuses and "搜索" in statuses[0][0]
