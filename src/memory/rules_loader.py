"""Rules 目录加载器：支持多层级加载和条件匹配。"""

from __future__ import annotations

import fnmatch
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.infra.paths import global_config_dir, managed_config_dir, project_config_dir

_MAX_RULES_CHARS = 2000

_cache_lock = threading.Lock()
_all_rules_cache: list[RuleFile] | None = None
_all_rules_fp: tuple[Any, ...] | None = None
_all_rules_root: str | None = None


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


def _rules_dirs(project_root: Path | None) -> list[Path]:
    return [
        managed_config_dir() / "rules",
        global_config_dir() / "rules",
        project_config_dir(project_root) / "rules",
        project_config_dir(project_root) / "rules.local",
    ]


def _compute_rules_fingerprint(dirs: list[Path]) -> tuple[Any, ...]:
    parts: list[tuple[str, int, int]] = []
    for base in dirs:
        try:
            if not base.is_dir():
                parts.append((str(base), 0, 0))
                continue
            for path in sorted(base.glob("*.md")):
                try:
                    st = path.stat()
                    parts.append((str(path.resolve()), st.st_mtime_ns, st.st_size))
                except OSError:
                    continue
        except OSError:
            parts.append((str(base), 0, 0))
    return tuple(parts)


def rules_fingerprint(project_root: Path | None = None) -> tuple[Any, ...]:
    return _compute_rules_fingerprint(_rules_dirs(project_root))


def invalidate_rules_cache() -> None:
    global _all_rules_cache, _all_rules_fp, _all_rules_root
    with _cache_lock:
        _all_rules_cache = None
        _all_rules_fp = None
        _all_rules_root = None


def _load_all_rules_uncached(project_root: Path | None) -> list[RuleFile]:
    rules: list[RuleFile] = []
    visited: set[Path] = set()
    for dir_path in _rules_dirs(project_root):
        if not dir_path.is_dir():
            continue
        for path in sorted(dir_path.glob("*.md")):
            if path in visited:
                continue
            visited.add(path)
            rule = _load_rule_file(path)
            if rule:
                rules.append(rule)
    rules.sort(
        key=lambda r: (r.priority == "high", r.priority == "medium", r.priority == "low"),
        reverse=True,
    )
    return rules


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
    global _all_rules_cache, _all_rules_fp, _all_rules_root
    root_key = "" if project_root is None else str(Path(project_root).resolve())
    dirs = _rules_dirs(project_root)
    fingerprint = _compute_rules_fingerprint(dirs)
    with _cache_lock:
        if (
            _all_rules_cache is not None
            and _all_rules_fp == fingerprint
            and _all_rules_root == root_key
        ):
            all_rules = _all_rules_cache
        else:
            all_rules = _load_all_rules_uncached(project_root)
            _all_rules_cache = all_rules
            _all_rules_fp = fingerprint
            _all_rules_root = root_key
    return [r for r in all_rules if _match_paths(r, current_file)]


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
