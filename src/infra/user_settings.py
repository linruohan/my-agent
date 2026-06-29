from __future__ import annotations

import json
import os
import re
import uuid
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


def merge_all_providers(
    base_providers: dict[str, ProviderConfig],
    user_settings: dict[str, Any],
) -> tuple[str, dict[str, ProviderConfig]]:
    """合并内置 Provider、用户覆盖与用户自定义 Provider。"""
    default, merged = merge_provider_configs(base_providers, user_settings)

    user_provs = user_settings.get("user_providers", {}) or {}
    for name, data in user_provs.items():
        merged[name] = ProviderConfig.from_dict(name, dict(data))

    hidden = set(user_settings.get("hidden_providers", []) or [])
    for name in hidden:
        merged.pop(name, None)

    if default not in merged and merged:
        default = next(iter(merged))
    return default, merged


def provider_display_name(name: str, user_settings: dict[str, Any] | None = None) -> str:
    settings = user_settings if user_settings is not None else load_user_settings()
    for bucket in ("providers", "user_providers"):
        ov = (settings.get(bucket) or {}).get(name, {})
        dn = (ov.get("display_name") or "").strip()
        if dn:
            return dn
    return name


def is_user_provider(name: str, user_settings: dict[str, Any] | None = None) -> bool:
    settings = user_settings if user_settings is not None else load_user_settings()
    return name in (settings.get("user_providers") or {})


def _api_key_env_for_user_provider(name: str) -> str:
    safe = re.sub(r"[^A-Z0-9_]", "_", name.upper())
    return f"USER_PROVIDER_{safe}"


def _new_user_provider_id(display_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", display_name.strip().lower()).strip("-")
    suffix = uuid.uuid4().hex[:6]
    return f"user-{slug or 'provider'}-{suffix}"


def provider_to_user_dict(provider: ProviderConfig, display_name: str | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "model": provider.model,
        "temperature": provider.temperature,
    }
    if display_name:
        data["display_name"] = display_name
    if provider.base_url:
        data["base_url"] = provider.base_url
    if provider.timeout != 60:
        data["timeout"] = provider.timeout
    return data


def user_provider_to_dict(provider: ProviderConfig, display_name: str) -> dict[str, Any]:
    data: dict[str, Any] = {
        "display_name": display_name,
        "type": provider.type,
        "model": provider.model,
        "temperature": provider.temperature,
        "api_key_env": provider.api_key_env or _api_key_env_for_user_provider(provider.name),
        "timeout": provider.timeout,
        "supports_tool_call": provider.supports_tool_call,
    }
    if provider.base_url:
        data["base_url"] = provider.base_url
    return data


def save_provider_entry(
    name: str,
    provider: ProviderConfig,
    *,
    display_name: str,
    is_user: bool,
) -> None:
    settings = load_user_settings()
    dn = display_name.strip() or name
    if is_user:
        bucket = settings.setdefault("user_providers", {})
        bucket[name] = user_provider_to_dict(provider, dn)
    else:
        bucket = settings.setdefault("providers", {})
        entry = provider_to_user_dict(provider, dn)
        bucket[name] = entry
    save_user_settings(settings)


def delete_provider_entry(name: str, *, is_user: bool) -> None:
    settings = load_user_settings()
    if is_user:
        user_provs = settings.get("user_providers") or {}
        user_provs.pop(name, None)
        settings["user_providers"] = user_provs
    else:
        hidden = settings.setdefault("hidden_providers", [])
        if name not in hidden:
            hidden.append(name)
    if settings.get("default_provider") == name:
        remaining = _list_visible_provider_names(settings)
        settings["default_provider"] = remaining[0] if remaining else settings.get("default_provider")
    save_user_settings(settings)


def _list_visible_provider_names(settings: dict[str, Any]) -> list[str]:
    from src.infra.config import load_llm_providers_config
    from src.llm.providers import parse_providers

    _, base = parse_providers(load_llm_providers_config())
    _, merged = merge_all_providers(base, settings)
    return list(merged.keys())


def activate_provider(name: str) -> None:
    settings = load_user_settings()
    settings["default_provider"] = name
    save_user_settings(settings)


def create_user_provider(payload: dict[str, Any]) -> tuple[str, ProviderConfig]:
    display_name = (payload.get("display_name") or "").strip() or "自定义提供商"
    name = _new_user_provider_id(display_name)
    api_key_env = _api_key_env_for_user_provider(name)
    provider = ProviderConfig.from_dict(
        name,
        {
            "type": payload.get("type") or "openai_compatible",
            "base_url": (payload.get("base_url") or "").strip() or None,
            "model": (payload.get("model") or "").strip(),
            "api_key_env": api_key_env,
            "temperature": float(payload.get("temperature", 0.7)),
            "timeout": int(payload.get("timeout", 60)),
            "supports_tool_call": True,
        },
    )
    save_provider_entry(name, provider, display_name=display_name, is_user=True)
    return name, provider


def persist_provider_choice(name: str, provider: ProviderConfig, display_name: str | None = None) -> None:
    """保存当前 Provider 选择与参数覆盖。"""
    settings = load_user_settings()
    settings["default_provider"] = name
    is_user = is_user_provider(name, settings)
    dn = display_name or provider_display_name(name, settings)
    if is_user:
        providers = settings.setdefault("user_providers", {})
        providers[name] = user_provider_to_dict(provider, dn)
    else:
        providers = settings.setdefault("providers", {})
        providers[name] = provider_to_user_dict(provider, dn)
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
