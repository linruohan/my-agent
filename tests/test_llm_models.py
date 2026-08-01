from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.llm.models import list_provider_models, list_provider_models_safe
from src.llm.providers import ProviderConfig
from src.ui.ui_prefs import get_chat_width_pct, persist_chat_width_pct


def test_chat_width_pct_roundtrip(tmp_path, monkeypatch):
    from src.infra import user_settings

    path = tmp_path / "user_settings.yaml"
    monkeypatch.setattr(user_settings, "USER_SETTINGS_PATH", path)
    assert get_chat_width_pct() == 100
    assert persist_chat_width_pct(70) == 70
    assert get_chat_width_pct() == 70
    assert persist_chat_width_pct(999) == 100
    assert persist_chat_width_pct(10) == 50


def test_list_openai_models():
    provider = ProviderConfig.from_dict(
        "test",
        {
            "type": "openai_compatible",
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4o",
            "api_key_env": "TEST_KEY",
        },
    )
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "data": [{"id": "gpt-4o-mini"}, {"id": "gpt-4o"}],
    }
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_resp

    with patch("src.llm.models.resolve_api_key", return_value="sk-test"):
        with patch("src.llm.models.httpx.Client", return_value=mock_client):
            models = list_provider_models(provider)

    assert models == ["gpt-4o", "gpt-4o-mini"]
    mock_client.get.assert_called_once()
    args, kwargs = mock_client.get.call_args
    assert args[0] == "https://api.example.com/v1/models"
    assert kwargs["headers"]["Authorization"] == "Bearer sk-test"


def test_list_ollama_models():
    provider = ProviderConfig.from_dict(
        "ollama",
        {"type": "ollama", "base_url": "http://localhost:11434", "model": "qwen2.5:7b"},
    )
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"models": [{"name": "llama3:latest"}, {"name": "qwen2.5:7b"}]}
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_resp

    with patch("src.llm.models.httpx.Client", return_value=mock_client):
        models = list_provider_models(provider)

    assert "qwen2.5:7b" in models
    assert "llama3:latest" in models


def test_list_provider_models_safe_on_error():
    provider = ProviderConfig.from_dict(
        "bad",
        {"type": "openai_compatible", "base_url": "", "model": "fallback-model"},
    )
    models, error = list_provider_models_safe(provider)
    assert models == ["fallback-model"]
    assert error
