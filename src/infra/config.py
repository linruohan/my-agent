from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.infra.paths import CONFIG_DIR, DATA_DIR, INSTALL_ROOT
from src.infra.user_settings import get_stored_api_key, save_stored_api_key

_yaml_cache: dict[Path, tuple[float, dict[str, Any]]] = {}


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _yaml_cache_key(path: Path) -> tuple[int, int]:
    st = path.stat()
    return st.st_mtime_ns, st.st_size


def _load_yaml_cached(path: Path) -> dict[str, Any]:
    """按文件 mtime+size 缓存 YAML，避免热路径重复读盘。"""
    if not path.is_file():
        return {}
    key = _yaml_cache_key(path)
    cached = _yaml_cache.get(path)
    if cached and cached[0] == key:
        return cached[1]
    data = _load_yaml(path)
    _yaml_cache[path] = (key, data)
    return data


def invalidate_yaml_cache() -> None:
    """清除 YAML 缓存（测试或热重载配置时使用）。"""
    _yaml_cache.clear()


def load_app_config() -> dict[str, Any]:
    cfg = _load_yaml_cached(CONFIG_DIR / "app.yaml")
    paths = cfg.setdefault("paths", {})
    for key in ("checkpoints", "workspace", "vectorstore"):
        rel = paths.get(key, f"data/{key}")
        paths[key] = str((INSTALL_ROOT / rel).resolve())
    return cfg


def load_llm_providers_config() -> dict[str, Any]:
    return _load_yaml_cached(CONFIG_DIR / "llm_providers.yaml")


def load_tools_config() -> dict[str, Any]:
    return _load_yaml_cached(CONFIG_DIR / "tools.yaml")


def load_search_config() -> dict[str, Any]:
    return _load_yaml_cached(CONFIG_DIR / "search.yaml")


def load_weather_config() -> dict[str, Any]:
    path = CONFIG_DIR / "weather.yaml"
    if not path.is_file():
        return {
            "province": "",
            "city": "",
            "district": "",
            "city_code": "101110101",
            "days": 7,
            "request_timeout": 20,
        }
    data = _load_yaml_cached(path)
    cfg = data.get("weather", data)
    return {
        "province": cfg.get("province", ""),
        "city": cfg.get("city", ""),
        "district": cfg.get("district", ""),
        "city_code": str(cfg.get("city_code", "101110101")),
        "days": int(cfg.get("days", 7) or 7),
        "request_timeout": float(cfg.get("request_timeout", 20) or 20),
    }


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
