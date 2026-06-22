"""AssistantController 消息路由集成测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.ui.input import INTENT_AGENT, INTENT_SEARCH, INTENT_SLASH_NOTE, InputIntent


@pytest.fixture
def controller(tmp_path, monkeypatch):
    """轻量 Controller：跳过 LLM/Agent 初始化，保留路由逻辑。"""
    import src.ui.controller.core as core_mod

    mock_graph = MagicMock()
    mock_graph.graph = MagicMock()
    mock_bundle = MagicMock()
    mock_bundle.graph = mock_graph.graph
    mock_bundle.close = MagicMock()

    mock_llm = MagicMock()
    monkeypatch.setattr(core_mod, "build_agent_graph", lambda llm, ckpt: mock_bundle)
    monkeypatch.setattr(
        core_mod,
        "create_llm_with_fallback",
        lambda providers, chain: (mock_llm, chain[0]),
    )
    monkeypatch.setattr(core_mod, "migrate_legacy_todos_json", lambda store: None)
    monkeypatch.setattr(
        core_mod,
        "TaskReminderService",
        lambda store: MagicMock(start=MagicMock(), stop=MagicMock()),
    )
    monkeypatch.setattr(core_mod, "DATA_DIR", tmp_path / "data", raising=False)

    import src.infra.paths as paths_mod

    monkeypatch.setattr(paths_mod, "DATA_DIR", tmp_path / "data")

    from src.ui.controller import AssistantController

    ctrl = AssistantController()
    ctrl.chat = MagicMock()
    return ctrl


def test_send_message_rejects_empty(controller):
    assert controller.send_message({"text": "   ", "attachments": []}) is False
    controller.chat.append_error.assert_called_once()


def test_process_slash_note(controller):
    intent = InputIntent(kind=INTENT_SLASH_NOTE, reason="test", slash_args="list")
    with patch("src.ui.controller.turns.handle_note_command", return_value="笔记列表") as mock_cmd:
        controller._handle_slash_note(intent)
    mock_cmd.assert_called_once()
    controller.chat.append_assistant_complete.assert_called_with("笔记列表")


def test_process_search_turn_starts_thread(controller):
    controller._llm = MagicMock()
    with patch("src.ui.controller.turns.threading.Thread") as mock_thread:
        controller._start_search_turn("Python 教程")
    assert controller._running is True
    mock_thread.assert_called_once()


def test_lookup_search_cache_dedupes(controller):
    controller._search_cache.lookup = MagicMock(return_value="cached answer")
    hit = controller._lookup_search_cache("q", "q", "other")
    assert hit == "cached answer"
    assert controller._search_cache.lookup.call_count == 1


def test_process_send_message_routes_search(controller, monkeypatch):
    intent = InputIntent(kind=INTENT_SEARCH, reason="slash:/search", search_query="天气")
    monkeypatch.setattr(
        "src.ui.controller.router.resolve_input_intent",
        lambda text, attachments, llm=None: intent,
    )
    controller._lookup_search_cache = MagicMock(return_value="cached answer")
    controller._start_search_turn = MagicMock()

    controller._process_send_message("/search 天气", [])

    controller._start_search_turn.assert_called_once_with("天气")
    controller._lookup_search_cache.assert_not_called()
    assert controller._compose_busy is False or controller._running is True


def test_process_send_message_search_requires_query(controller, monkeypatch):
    intent = InputIntent(kind=INTENT_SEARCH, reason="slash:/search", search_query="")
    monkeypatch.setattr(
        "src.ui.controller.router.resolve_input_intent",
        lambda text, attachments, llm=None: intent,
    )
    controller._start_search_turn = MagicMock()

    controller._process_send_message("/search", [])

    controller._start_search_turn.assert_not_called()
    controller.chat.append_error.assert_called_once()


def test_process_send_message_cache_before_agent(controller, monkeypatch):
    intent = InputIntent(kind=INTENT_AGENT, reason="fallback:agent")
    monkeypatch.setattr(
        "src.ui.controller.router.resolve_input_intent",
        lambda text, attachments, llm=None: intent,
    )
    controller._lookup_search_cache = MagicMock(return_value="cached answer")
    controller._deliver_cached_search = MagicMock()
    controller._start_agent_turn = MagicMock()

    controller._process_send_message("今日头条", [])

    controller._lookup_search_cache.assert_called()
    controller._deliver_cached_search.assert_called_once_with("今日头条", "cached answer")
    controller._start_agent_turn.assert_not_called()


def test_process_send_message_agent_when_cache_miss(controller, monkeypatch):
    intent = InputIntent(kind=INTENT_AGENT, reason="fallback:agent")
    monkeypatch.setattr(
        "src.ui.controller.router.resolve_input_intent",
        lambda text, attachments, llm=None: intent,
    )
    monkeypatch.setattr(
        "src.ui.controller.router.compose_user_message",
        lambda text, attachments: {"ok": True, "message": text, "errors": []},
    )
    controller._lookup_search_cache = MagicMock(return_value=None)
    controller._start_agent_turn = MagicMock()
    controller.runner.graph = MagicMock()

    controller._process_send_message("写一段 Python", [])

    controller._start_agent_turn.assert_called_once()
