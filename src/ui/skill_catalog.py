"""兼容层：请使用 src.ui.skill.catalog。"""
from src.ui.skill.catalog import (
    SYSTEM_SLASH_TOOLS,
    build_slash_catalog,
    get_skill_dirs,
    load_skill_prompt,
    resolve_skill,
    scan_skills,
)

__all__ = [
    "SYSTEM_SLASH_TOOLS",
    "build_slash_catalog",
    "get_skill_dirs",
    "load_skill_prompt",
    "resolve_skill",
    "scan_skills",
]
