"""settings.json 读写：critical_rules 等用户/项目级配置，禁止写 config/。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from src.infra.config import invalidate_json_cache, load_merged_settings
from src.infra.paths import project_config_dir


def local_settings_path(project_root: Path | None = None) -> Path:
    return project_config_dir(project_root) / "settings.local.json"


def _load_local_settings(project_root: Path | None = None) -> dict[str, Any]:
    path = local_settings_path(project_root)
    if not path.is_file():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f) or {}
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("读取 settings.local.json 失败: {}", exc)
        return {}


def _save_local_settings(data: dict[str, Any], project_root: Path | None = None) -> None:
    path = local_settings_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    invalidate_json_cache()


def upsert_critical_rule(
    name: str,
    content: str,
    project_root: Path | None = None,
) -> None:
    """将绝对禁止规则写入项目本地 settings.local.json。"""
    data = _load_local_settings(project_root)
    rules = data.setdefault("critical_rules", [])
    if not isinstance(rules, list):
        rules = []
        data["critical_rules"] = rules

    today = datetime.now().strftime("%Y-%m-%d")
    existing = next((r for r in rules if isinstance(r, dict) and r.get("name") == name), None)
    if existing:
        existing["content"] = content
        existing["updated"] = today
    else:
        rules.append(
            {
                "name": name,
                "content": content,
                "created": today,
                "updated": today,
            }
        )
    _save_local_settings(data, project_root)


def get_critical_rules(project_root: Path | None = None) -> list[dict[str, Any]]:
    """从四层合并 settings 读取 critical_rules。"""
    merged = load_merged_settings(project_root)
    rules = merged.get("critical_rules") or []
    return [r for r in rules if isinstance(r, dict) and r.get("name") and r.get("content")]


def build_critical_rules_prompt_block(project_root: Path | None = None) -> str:
    rules = get_critical_rules(project_root)
    if not rules:
        return ""
    lines = ["以下为强制约束，必须遵守："]
    for rule in rules:
        lines.append(f"- 【{rule['name']}】{str(rule['content']).strip()}")
    return "\n".join(lines)


def is_team_memory_enabled(project_root: Path | None = None) -> bool:
    merged = load_merged_settings(project_root)
    memory = merged.get("memory") or {}
    if isinstance(memory, dict):
        return bool(memory.get("team_memory_enabled", False))
    return False


def memory_stale_days(project_root: Path | None = None, default: int = 2) -> int:
    merged = load_merged_settings(project_root)
    memory = merged.get("memory") or {}
    if isinstance(memory, dict):
        try:
            return int(memory.get("stale_days", default) or default)
        except (TypeError, ValueError):
            return default
    return default
