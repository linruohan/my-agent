"""语音输入设置开关测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def controller(tmp_path, monkeypatch):
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

    return AssistantController()


def test_start_voice_rejected_when_disabled(controller, monkeypatch):
    monkeypatch.setattr("src.ui.controller.voice.is_voice_input_enabled", lambda: False)
    result = controller.start_voice_input()
    assert result["ok"] is False
    assert "未启用" in result["error"]


def test_get_voice_info_when_disabled(controller, monkeypatch):
    monkeypatch.setattr("src.ui.controller.voice.is_voice_input_enabled", lambda: False)
    info = controller.get_voice_info()
    assert info["supported"] is False
    assert info["enabled"] is False


def test_build_initial_state_voice_off_by_default(controller, monkeypatch):
    monkeypatch.setattr("src.ui.controller.settings.is_voice_input_enabled", lambda: False)
    state = controller.build_initial_state()
    assert state["composer_meta"]["voice_enabled"] is False
    assert state["composer_meta"]["voice_supported"] is False


def test_build_initial_state_probes_support_when_enabled(controller, monkeypatch):
    monkeypatch.setattr("src.ui.controller.settings.is_voice_input_enabled", lambda: True)
    with patch("src.ui.controller.settings.voice_is_supported", return_value=True):
        state = controller.build_initial_state()
    assert state["composer_meta"]["voice_enabled"] is True
    assert state["composer_meta"]["voice_supported"] is True
