"""AssistantController 消息路由集成测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.ui.input import INTENT_SEARCH, INTENT_SLASH_NOTE, InputIntent


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
    intent = InputIntent(kind=INTENT_SEARCH, reason="rule", search_query="天气")
    monkeypatch.setattr(
        "src.ui.controller.router.resolve_input_intent",
        lambda text, attachments, llm=None: intent,
    )
    controller._lookup_search_cache = MagicMock(return_value=None)
    controller._start_search_turn = MagicMock()

    controller._process_send_message("天气", [])

    controller._start_search_turn.assert_called_once_with("天气")
    assert controller._compose_busy is False or controller._running is True
