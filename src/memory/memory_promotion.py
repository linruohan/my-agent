"""记忆提权协议：自动将行为规则提升到指导层。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from src.infra.paths import project_config_dir
from src.memory.memory_index import write_memory_index

INSTRUCTION_WORDS = ["必须", "不要", "禁止", "不能", "应该", "应当", "切勿"]
CRITICAL_WORDS = ["绝对不要", "永远禁止", "绝对禁止", "切勿"]


def _detect_rule_type(content: str) -> str:
    """检测内容类型：background / rule / critical。"""
    if content is None:
        return "background"

    content_lower = content.lower()

    for word in CRITICAL_WORDS:
        if word in content:
            return "critical"

    for word in INSTRUCTION_WORDS:
        if word in content:
            return "rule"

    return "background"


def _generate_rule_file_name(name: str) -> str:
    """生成规则文件名。"""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        slug = "rule"
    return f"{slug}.md"


def _format_rule_content(name: str, description: str, content: str) -> str:
    """格式化规则文件内容。"""
    now = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "---",
        f'name: "{name}"',
        f'paths: []',
        f'priority: "high"',
        "---",
        "",
        content.strip(),
    ]
    return "\n".join(lines)


def _update_settings_critical(name: str, content: str) -> None:
    """将绝对禁止规则写入 settings.json。"""
    from src.infra.config import load_app_config

    cfg = load_app_config()
    critical_rules = cfg.setdefault("critical_rules", [])

    existing = next((r for r in critical_rules if r.get("name") == name), None)
    if existing:
        existing["content"] = content
        existing["updated"] = datetime.now().strftime("%Y-%m-%d")
    else:
        critical_rules.append({
            "name": name,
            "content": content,
            "created": datetime.now().strftime("%Y-%m-%d"),
            "updated": datetime.now().strftime("%Y-%m-%d"),
        })

    from src.infra.config import CONFIG_DIR

    import yaml

    with (CONFIG_DIR / "app.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, default_flow_style=False, allow_unicode=True)


def promote_memory(
    memory_content: str,
    memory_name: str,
    memory_description: str,
    project_root: Path | None = None,
) -> str | None:
    """根据记忆内容判断是否需要提权，并执行提权操作。"""
    if memory_content is None or memory_name is None:
        return None

    rule_type = _detect_rule_type(memory_content)

    if rule_type == "background":
        return "内容为背景知识，无需提权"

    if rule_type == "critical":
        _update_settings_critical(memory_name, memory_content)
        logger.info(f"记忆提权到 settings.json: {memory_name}")
        return f"记忆「{memory_name}」已提权到 settings.json（强制约束）"

    if rule_type == "rule":
        rules_dir = project_config_dir(project_root) / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)

        file_name = _generate_rule_file_name(memory_name)
        file_path = rules_dir / file_name

        if file_path.is_file():
            existing = file_path.read_text(encoding="utf-8", errors="ignore")
            if memory_content.strip() in existing:
                logger.debug(f"跳过重复规则: {file_name}")
                return f"规则「{memory_name}」已存在，无需重复提权"

        formatted = _format_rule_content(memory_name, memory_description, memory_content)
        file_path.write_text(formatted + "\n", encoding="utf-8")
        logger.info(f"记忆提权到 rules/: {file_name}")
        write_memory_index(project_root)
        return f"记忆「{memory_name}」已提权到 .my-agent/rules/（强约束力）"

    return "未知类型，未提权"