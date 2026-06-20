from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from src.infra.paths import DATA_DIR
from src.llm.providers import ProviderConfig

USER_SETTINGS_PATH = DATA_DIR / "user_settings.yaml"
SECRETS_PATH = DATA_DIR / "secrets.json"
KEYRING_SERVICE = "my-agent"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def load_user_settings() -> dict[str, Any]:
    return _load_yaml(USER_SETTINGS_PATH)


def save_user_settings(settings: dict[str, Any]) -> None:
    _save_yaml(USER_SETTINGS_PATH, settings)


def merge_provider_configs(
    base_providers: dict[str, ProviderConfig],
    user_settings: dict[str, Any],
) -> tuple[str, dict[str, ProviderConfig]]:
    """将用户覆盖配置合并到默认 Provider 配置。"""
    default = user_settings.get("default_provider")
    overrides = user_settings.get("providers", {})
    merged: dict[str, ProviderConfig] = {}

    for name, base in base_providers.items():
        cfg = ProviderConfig.from_dict(
            name,
            {
                "type": base.type,
                "base_url": base.base_url,
                "model": base.model,
                "api_key_env": base.api_key_env,
                "temperature": base.temperature,
                "timeout": base.timeout,
                "supports_tool_call": base.supports_tool_call,
            },
        )
        if name in overrides:
            ov = overrides[name]
            if "model" in ov:
                cfg.model = ov["model"]
            if "base_url" in ov:
                cfg.base_url = ov["base_url"]
            if "temperature" in ov:
                cfg.temperature = float(ov["temperature"])
            if "timeout" in ov:
                cfg.timeout = int(ov["timeout"])
        merged[name] = cfg

    if not default or default not in merged:
        default = next(iter(merged))
    return default, merged


def provider_to_user_dict(provider: ProviderConfig) -> dict[str, Any]:
    data: dict[str, Any] = {
        "model": provider.model,
        "temperature": provider.temperature,
    }
    if provider.base_url:
        data["base_url"] = provider.base_url
    if provider.timeout != 60:
        data["timeout"] = provider.timeout
    return data


def persist_provider_choice(name: str, provider: ProviderConfig) -> None:
    """保存当前 Provider 选择与参数覆盖。"""
    settings = load_user_settings()
    settings["default_provider"] = name
    providers = settings.setdefault("providers", {})
    providers[name] = provider_to_user_dict(provider)
    save_user_settings(settings)
    logger.info("用户设置已保存: provider={}", name)


def _load_secrets_file() -> dict[str, str]:
    if not SECRETS_PATH.exists():
        return {}
    try:
        with SECRETS_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if isinstance(v, str)}
    except Exception as exc:
        logger.warning("读取 secrets 文件失败: {}", exc)
        return {}


def _save_secrets_file(secrets: dict[str, str]) -> None:
    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SECRETS_PATH.open("w", encoding="utf-8") as f:
        json.dump(secrets, f, ensure_ascii=False, indent=2)


def get_stored_api_key(env_name: str) -> str | None:
    value = os.environ.get(env_name)
    if value:
        return value
    try:
        import keyring

        keyring_value = keyring.get_password(KEYRING_SERVICE, env_name)
        if keyring_value:
            return keyring_value
    except Exception as exc:
        logger.debug("keyring 读取失败 ({}): {}", env_name, exc)
    return _load_secrets_file().get(env_name)


def save_stored_api_key(env_name: str, api_key: str) -> None:
    saved = False
    try:
        import keyring

        keyring.set_password(KEYRING_SERVICE, env_name, api_key)
        saved = True
        logger.info("API Key 已写入系统密钥链: {}", env_name)
    except Exception as exc:
        logger.warning("keyring 写入失败，改用本地文件: {}", exc)

    secrets = _load_secrets_file()
    secrets[env_name] = api_key
    _save_secrets_file(secrets)
    if not saved:
        logger.info("API Key 已写入本地 secrets 文件: {}", env_name)


def has_stored_api_key(env_name: str | None) -> bool:
    if not env_name:
        return False
    key = get_stored_api_key(env_name)
    return bool(key and key.strip())
