from __future__ import annotations

import pytest

from src.llm.providers import ProviderConfig, parse_providers


def test_parse_providers():
    raw = {
        "default_provider": "deepseek",
        "providers": {
            "deepseek": {
                "type": "openai_compatible",
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-chat",
                "api_key_env": "DEEPSEEK_API_KEY",
            }
        },
    }
    default, providers = parse_providers(raw)
    assert default == "deepseek"
    assert "deepseek" in providers
    assert providers["deepseek"].model == "deepseek-chat"


def test_provider_from_dict():
    cfg = ProviderConfig.from_dict(
        "test",
        {"type": "ollama", "model": "qwen2.5:7b", "base_url": "http://localhost:11434"},
    )
    assert cfg.type == "ollama"
    assert cfg.model == "qwen2.5:7b"
