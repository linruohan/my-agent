from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.agent.hitl import (
    format_approval_description,
    get_pending_tool_calls,
    is_interrupted_before_tools,
    needs_user_approval,
    reject_pending_tools,
)
from langchain_core.messages import AIMessage


def test_needs_user_approval():
    calls = [{"name": "create_calendar_event", "args": {"title": "会议"}}]
    assert needs_user_approval(calls) is True
    assert needs_user_approval([{"name": "web_search", "args": {}}]) is False


def test_format_approval_description():
    calls = [{"name": "create_calendar_event", "args": {"title": "周会", "date": "2026-06-20"}}]
    text = format_approval_description(calls)
    assert "create_calendar_event" in text
    assert "周会" in text


def test_reject_pending_tools():
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "create_calendar_event", "id": "call_1", "args": {"title": "x"}},
                    {"name": "web_search", "id": "call_2", "args": {"query": "q"}},
                ],
            )
        ]
    }
    msgs = reject_pending_tools(state)
    assert len(msgs) == 1
    assert msgs[0].name == "create_calendar_event"


def test_is_interrupted_before_tools():
    snap = MagicMock()
    snap.next = ("tools",)
    assert is_interrupted_before_tools(snap) is True
    snap.next = ("agent",)
    assert is_interrupted_before_tools(snap) is False


def test_search_bing_parse():
    html = """
    <ol id="b_results">
      <li class="b_algo">
        <h2><a href="https://example.com">Test Title</a></h2>
        <div class="b_caption"><p>Test snippet content</p></div>
      </li>
    </ol>
    """
    with patch("src.tools.search.httpx.Client") as mock_client:
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        mock_client.return_value.__enter__.return_value.get.return_value = mock_resp
        from src.tools.search import search_bing

        results = search_bing("test", max_results=3)
        assert len(results) == 1
        assert results[0].title == "Test Title"
        assert results[0].engine == "bing"
