from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.infra.paths import CONFIG_DIR, DATA_DIR, PROJECT_ROOT
from src.infra.user_settings import get_stored_api_key, save_stored_api_key


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_app_config() -> dict[str, Any]:
    cfg = _load_yaml(CONFIG_DIR / "app.yaml")
    paths = cfg.setdefault("paths", {})
    for key in ("checkpoints", "workspace", "vectorstore"):
        rel = paths.get(key, f"data/{key}")
        paths[key] = str((PROJECT_ROOT / rel).resolve())
    return cfg


def load_llm_providers_config() -> dict[str, Any]:
    return _load_yaml(CONFIG_DIR / "llm_providers.yaml")


def load_tools_config() -> dict[str, Any]:
    return _load_yaml(CONFIG_DIR / "tools.yaml")


def load_search_config() -> dict[str, Any]:
    return _load_yaml(CONFIG_DIR / "search.yaml")


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for sub in ("checkpoints", "workspace", "vectorstore"):
        (DATA_DIR / sub).mkdir(parents=True, exist_ok=True)


def get_env_or_keyring(env_name: str, service: str = "my-agent") -> str | None:
    return get_stored_api_key(env_name)


def save_api_key(env_name: str, api_key: str, service: str = "my-agent") -> None:
    save_stored_api_key(env_name, api_key)


def load_merged_providers():
    """加载默认 Provider 配置并合并用户覆盖项。"""
    from src.infra.user_settings import load_user_settings, merge_provider_configs
    from src.llm.providers import parse_providers

    raw = load_llm_providers_config()
    yaml_default, base_providers = parse_providers(raw)
    user_settings = load_user_settings()
    if user_settings:
        return merge_provider_configs(base_providers, user_settings)
    return yaml_default, base_providers
