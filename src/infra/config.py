from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from src.infra.paths import CONFIG_DIR, DATA_DIR, INSTALL_ROOT, global_config_dir, managed_config_dir, project_config_dir
from src.infra.user_settings import get_stored_api_key, save_stored_api_key

_yaml_cache: dict[Path, tuple[float, dict[str, Any]]] = {}
_json_cache: dict[Path, tuple[float, dict[str, Any]]] = {}


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


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f) or {}
    except json.JSONDecodeError:
        from loguru import logger

        logger.warning(f"无效 JSON 文件，已跳过: {path}")
        return {}


def _json_cache_key(path: Path) -> tuple[int, int]:
    st = path.stat()
    return st.st_mtime_ns, st.st_size


def _load_json_cached(path: Path) -> dict[str, Any]:
    """按文件 mtime+size 缓存 JSON，避免热路径重复读盘。"""
    if not path.is_file():
        return {}
    key = _json_cache_key(path)
    cached = _json_cache.get(path)
    if cached and cached[0] == key:
        return cached[1]
    data = _load_json(path)
    _json_cache[path] = (key, data)
    return data


def _merge_configs(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """合并配置字典，数组类型合并，标量类型覆盖。"""
    result = base.copy()
    for key, value in overlay.items():
        if key in result:
            if isinstance(result[key], list) and isinstance(value, list):
                result[key] = result[key] + [v for v in value if v not in result[key]]
            elif isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = _merge_configs(result[key], value)
            else:
                result[key] = value
        else:
            result[key] = value
    return result


def invalidate_yaml_cache() -> None:
    """清除 YAML 缓存（测试或热重载配置时使用）。"""
    _yaml_cache.clear()


def invalidate_json_cache() -> None:
    """清除 JSON 缓存（测试或热重载配置时使用）。"""
    _json_cache.clear()


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


def _run_memory_migration() -> None:
    """检测旧格式 MEMORY.md 并自动执行迁移。"""
    old_memory_path = DATA_DIR / "workspace" / "MEMORY.md"
    new_memory_dir = project_config_dir() / "memory"

    if not old_memory_path.is_file():
        return

    backup_path = old_memory_path.with_suffix(".md.bak")
    if not backup_path.is_file():
        import shutil

        shutil.copy2(old_memory_path, backup_path)

    from scripts.migrate_memory_v1_to_v2 import _migrate_v1_to_v2

    try:
        migrated = _migrate_v1_to_v2(old_memory_path, new_memory_dir)
        if migrated > 0:
            from loguru import logger

            logger.info(f"[memory] 自动迁移完成，共迁移 {migrated} 条记忆")
    except Exception:
        from loguru import logger

        logger.exception("[memory] 自动迁移失败")


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for sub in ("checkpoints", "workspace", "vectorstore"):
        (DATA_DIR / sub).mkdir(parents=True, exist_ok=True)
    from src.database import ensure_database
    from src.memory.config_init import init_all_configs
    from src.memory.context_files import ensure_context_files

    ensure_context_files()
    init_all_configs()
    _run_memory_migration()
    ensure_database()


def get_env_or_keyring(env_name: str, service: str = "my-agent") -> str | None:
    return get_stored_api_key(env_name)


def save_api_key(env_name: str, api_key: str, service: str = "my-agent") -> None:
    save_stored_api_key(env_name, api_key)


def load_merged_settings(project_root: Path | None = None) -> dict[str, Any]:
    """加载并合并四层 settings.json 配置（优先级从低到高）。
    
    加载顺序：System → Global → Project → Local
    合并规则：数组类型跨层合并，标量类型取最具体的值
    """
    layers = [
        managed_config_dir() / "settings.json",
        global_config_dir() / "settings.json",
        project_config_dir(project_root) / "settings.json",
        project_config_dir(project_root) / "settings.local.json",
    ]

    merged: dict[str, Any] = {}
    for layer_path in layers:
        layer_config = _load_json_cached(layer_path)
        merged = _merge_configs(merged, layer_config)

    return merged


def load_merged_providers():
    """加载默认 Provider 配置并合并用户覆盖项。"""
    from src.infra.user_settings import load_user_settings, merge_all_providers
    from src.llm.providers import parse_providers

    raw = load_llm_providers_config()
    yaml_default, base_providers = parse_providers(raw)
    user_settings = load_user_settings()
    if user_settings:
        return merge_all_providers(base_providers, user_settings)
    return yaml_default, base_providers
