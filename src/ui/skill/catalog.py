"""Skill 目录扫描与斜杠命令目录。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.infra.paths import DATA_DIR
from src.infra.user_settings import load_user_settings


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
    from src.ui.skill.catalog import default_skills_dir

    workspace_skills = default_skills_dir()
    if workspace_skills not in dirs:
        dirs.append(workspace_skills)
    return dirs


def scan_skills() -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    seen: set[str] = set()
    for base in get_skill_dirs():
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
