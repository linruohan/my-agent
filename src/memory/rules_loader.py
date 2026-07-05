"""Rules 目录加载器：支持多层级加载和条件匹配。"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.infra.paths import global_config_dir, managed_config_dir, project_config_dir

_MAX_RULES_CHARS = 2000


@dataclass
class RuleFile:
    path: Path
    name: str
    description: str
    paths: list[str]
    priority: str
    content: str


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---\n")
    if end == -1:
        return {}, text
    try:
        frontmatter = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        frontmatter = {}
    body = text[end + 5 :].strip()
    return frontmatter, body


def _load_rule_file(path: Path) -> RuleFile | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return None
    if not text:
        return None
    frontmatter, body = _parse_frontmatter(text)
    return RuleFile(
        path=path,
        name=frontmatter.get("name", path.stem),
        description=frontmatter.get("description", ""),
        paths=frontmatter.get("paths", []),
        priority=frontmatter.get("priority", "medium"),
        content=body,
    )


def _match_paths(rule: RuleFile, current_file: str | None) -> bool:
    if not rule.paths or not current_file:
        return True
    current_path = Path(current_file).as_posix()
    for pattern in rule.paths:
        if fnmatch.fnmatch(current_path, pattern):
            return True
    return False


def load_rules(
    current_file: str | None = None,
    project_root: Path | None = None,
) -> list[RuleFile]:
    """加载所有适用的规则文件。

    Args:
        current_file: 当前编辑的文件路径，用于条件匹配
        project_root: 项目根目录，默认为当前项目

    Returns:
        匹配的规则文件列表，按优先级排序（项目规则优先）
    """
    rules: list[RuleFile] = []
    visited = set()

    def _load_rules_from_dir(dir_path: Path, is_project: bool = False) -> None:
        if not dir_path.is_dir():
            return
        for path in sorted(dir_path.glob("*.md")):
            if path in visited:
                continue
            visited.add(path)
            rule = _load_rule_file(path)
            if rule and _match_paths(rule, current_file):
                rules.append(rule)

    _load_rules_from_dir(managed_config_dir() / "rules")
    _load_rules_from_dir(global_config_dir() / "rules")
    _load_rules_from_dir(project_config_dir(project_root) / "rules", is_project=True)
    _load_rules_from_dir(project_config_dir(project_root) / "rules.local", is_project=True)

    rules.sort(key=lambda r: (r.priority == "high", r.priority == "medium", r.priority == "low"), reverse=True)
    return rules


def build_rules_prompt_block(current_file: str | None = None, project_root: Path | None = None) -> str:
    """组装注入 system prompt 的规则块。"""
    rules = load_rules(current_file=current_file, project_root=project_root)
    if not rules:
        return ""
    parts = []
    total_chars = 0
    for rule in rules:
        rule_text = f"## {rule.name}\n{rule.content}"
        if total_chars + len(rule_text) > _MAX_RULES_CHARS:
            parts.append("…（规则已截断）")
            break
        parts.append(rule_text)
        total_chars += len(rule_text)
    return "\n\n".join(parts)