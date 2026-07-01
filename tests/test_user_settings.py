from __future__ import annotations

import json

from src.infra.user_settings import (
    get_stored_api_key,
    has_stored_api_key,
    load_user_settings,
    merge_all_providers,
    merge_provider_configs,
    persist_provider_choice,
    provider_is_ready,
    save_stored_api_key,
    save_user_settings,
)
from src.llm.providers import ProviderConfig, parse_providers


def _sample_providers() -> dict[str, ProviderConfig]:
    _, providers = parse_providers(
        {
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
    )
    return providers


def test_persist_provider_choice(tmp_path, monkeypatch):
    settings_file = tmp_path / "user_settings.yaml"
    monkeypatch.setattr("src.infra.user_settings.USER_SETTINGS_PATH", settings_file)

    providers = _sample_providers()
    p = providers["deepseek"]
    p.model = "deepseek-reasoner"
    persist_provider_choice("deepseek", p)

    saved = load_user_settings()
    assert saved["default_provider"] == "deepseek"
    assert saved["providers"]["deepseek"]["model"] == "deepseek-reasoner"


def test_merge_provider_configs():
    base = _sample_providers()
    user = {
        "default_provider": "deepseek",
        "providers": {"deepseek": {"model": "custom-model", "temperature": 0.5}},
    }
    default, merged = merge_provider_configs(base, user)
    assert default == "deepseek"
    assert merged["deepseek"].model == "custom-model"
    assert merged["deepseek"].temperature == 0.5


def test_merge_all_providers_user_default():
    base = _sample_providers()
    user = {
        "default_provider": "user-custom-abc123",
        "user_providers": {
            "user-custom-abc123": {
                "display_name": "My Custom",
                "type": "openai_compatible",
                "model": "gpt-4",
                "api_key_env": "USER_PROVIDER_USER_CUSTOM_ABC123",
                "temperature": 0.7,
            }
        },
    }
    default, merged = merge_all_providers(base, user)
    assert default == "user-custom-abc123"
    assert merged["user-custom-abc123"].model == "gpt-4"


def test_provider_is_ready():
    ollama = ProviderConfig.from_dict(
        "ollama",
        {"type": "ollama", "model": "qwen2.5:7b", "base_url": "http://localhost:11434"},
    )
    assert provider_is_ready(ollama)

    cloud = ProviderConfig.from_dict(
        "deepseek",
        {
            "type": "openai_compatible",
            "model": "deepseek-chat",
            "api_key_env": "DEEPSEEK_API_KEY",
        },
    )
    assert not provider_is_ready(cloud)


def test_api_key_file_fallback(tmp_path, monkeypatch):
    secrets_file = tmp_path / "secrets.json"
    monkeypatch.setattr("src.infra.user_settings.SECRETS_PATH", secrets_file)

    save_stored_api_key("TEST_API_KEY", "sk-test-12345")
    assert has_stored_api_key("TEST_API_KEY")
    assert get_stored_api_key("TEST_API_KEY") == "sk-test-12345"
    assert secrets_file.exists()

    data = json.loads(secrets_file.read_text(encoding="utf-8"))
    assert data["TEST_API_KEY"] == "sk-test-12345"
