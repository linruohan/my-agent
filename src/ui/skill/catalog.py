"""Skill 目录扫描与斜杠命令目录。"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from src.infra.paths import DATA_DIR
from src.infra.user_settings import load_user_settings

_cache_lock = threading.Lock()
_skills_cache: list[dict[str, Any]] | None = None
_skills_cache_fp: tuple[Any, ...] | None = None


def default_skills_dir() -> Path:
    path = DATA_DIR / "workspace" / "skills"
    path.mkdir(parents=True, exist_ok=True)
    return path

# 系统内置斜杠命令（tool）
SYSTEM_SLASH_TOOLS: list[dict[str, Any]] = [
    {"kind": "tool", "name": "note", "label": "/note", "desc": "笔记管理", "slash": "/note"},
    {"kind": "tool", "name": "tsk", "label": "/tsk", "desc": "任务管理", "slash": "/tsk"},
    {"kind": "tool", "name": "cache", "label": "/cache", "desc": "搜索缓存管理", "slash": "/cache"},
    {"kind": "tool", "name": "metrics", "label": "/metrics", "desc": "耗时指标", "slash": "/metrics"},
    {"kind": "tool", "name": "reload", "label": "/reload", "desc": "热重载配置与 Gateway", "slash": "/reload"},
    {"kind": "tool", "name": "search", "label": "/search", "desc": "网络搜索", "slash": "/search"},
    {"kind": "tool", "name": "weather", "label": "/weather", "desc": "天气预报", "slash": "/weather"},
    {"kind": "tool", "name": "ocr", "label": "/ocr", "desc": "图片 OCR", "slash": "/ocr"},
    {"kind": "tool", "name": "file", "label": "/file", "desc": "文件搜索：/file <关键字> 项目内搜索 | /file global <关键字> 系统搜索 | /file grep <内容>", "slash": "/file"},
]


def get_skill_dirs() -> list[Path]:
    settings = load_user_settings()
    ui = settings.get("ui", {}) or {}
    raw = ui.get("skill_dirs") or settings.get("skill_dirs") or []
    if isinstance(raw, str):
        raw = [raw]
    dirs: list[Path] = []
    for item in raw:
        p = Path(str(item)).expanduser()
        if p.is_dir():
            dirs.append(p.resolve())
    workspace_skills = default_skills_dir()
    if workspace_skills not in dirs:
        dirs.append(workspace_skills)
    return dirs


def _compute_skills_fingerprint(dirs: list[Path]) -> tuple[Any, ...]:
    """仅用 SKILL.md 路径 + mtime/size，避免反复读文件内容。"""
    parts: list[tuple[str, int, int]] = []
    for base in dirs:
        try:
            for skill_md in base.rglob("SKILL.md"):
                try:
                    st = skill_md.stat()
                    parts.append((str(skill_md.resolve()), st.st_mtime_ns, st.st_size))
                except OSError:
                    continue
        except OSError:
            continue
    parts.sort()
    return tuple(parts)


def invalidate_skill_catalog_cache() -> None:
    global _skills_cache, _skills_cache_fp
    with _cache_lock:
        _skills_cache = None
        _skills_cache_fp = None


def _scan_skills_uncached(dirs: list[Path]) -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    seen: set[str] = set()
    for base in dirs:
        for skill_md in base.rglob("SKILL.md"):
            folder = skill_md.parent
            name = folder.name
            if name in seen:
                continue
            seen.add(name)
            desc = ""
            try:
                text = skill_md.read_text(encoding="utf-8", errors="ignore")
                for line in text.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        desc = line[:80]
                        break
                    if line.startswith("# "):
                        desc = line.lstrip("# ").strip()[:80]
                        break
            except OSError:
                pass
            skills.append(
                {
                    "kind": "skill",
                    "name": name,
                    "label": f"/{name}",
                    "desc": desc or "Skill",
                    "slash": f"/{name}",
                    "path": str(skill_md),
                }
            )
    skills.sort(key=lambda s: s["name"].lower())
    return skills


def scan_skills() -> list[dict[str, Any]]:
    global _skills_cache, _skills_cache_fp
    dirs = get_skill_dirs()
    fingerprint = _compute_skills_fingerprint(dirs)
    with _cache_lock:
        if _skills_cache is not None and _skills_cache_fp == fingerprint:
            return [dict(item) for item in _skills_cache]
    skills = _scan_skills_uncached(dirs)
    with _cache_lock:
        _skills_cache = skills
        _skills_cache_fp = fingerprint
        return [dict(item) for item in _skills_cache]


def build_slash_catalog() -> list[dict[str, Any]]:
    return SYSTEM_SLASH_TOOLS + scan_skills()


def resolve_skill(skill_name: str) -> tuple[Path, Path] | None:
    """返回 (skill_root, skill_md_path)。"""
    name = skill_name.lstrip("/").strip()
    for item in scan_skills():
        if item["name"].lower() == name.lower():
            skill_md = Path(item["path"])
            return skill_md.parent.resolve(), skill_md.resolve()
    return None


def load_skill_prompt(skill_name: str) -> str | None:
    name = skill_name.lstrip("/").strip()
    resolved = resolve_skill(name)
    if not resolved:
        return None
    _, skill_md = resolved
    try:
        return skill_md.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
