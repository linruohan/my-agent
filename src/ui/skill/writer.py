"""Skill 文件创建与写入。"""

from __future__ import annotations

import re
from pathlib import Path

from src.ui.skill.catalog import default_skills_dir, get_skill_dirs, resolve_skill


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "-", (name or "").strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "skill"


def skill_target_dir(name: str) -> Path:
    slug = _slugify(name)
    for base in get_skill_dirs():
        candidate = base / slug
        if candidate.is_dir():
            return candidate
    return default_skills_dir() / slug


def create_skill_files(
    name: str,
    description: str,
    instructions: str,
    *,
    script_body: str = "",
) -> tuple[Path, bool]:
    """创建 SKILL.md 与可选 scripts/main.py。返回 (skill_root, created_new)。"""
    slug = _slugify(name)
    if resolve_skill(slug):
        raise ValueError(f"Skill「{slug}」已存在")

    root = default_skills_dir() / slug
    if root.exists():
        raise ValueError(f"目录已存在：{root}")

    root.mkdir(parents=True)
    desc = (description or slug).strip()
    body = (instructions or "").strip()
    skill_md = f"""# {desc}

{body}

## 使用方式

Agent 可通过 `get_skill_details` / `run_skill_tool` 调用本 Skill。
斜杠命令：`/{slug}`

## 参数

| 参数 | 短选项 | 必填 | 说明 |
|------|--------|------|------|
| input | - | 否 | 用户输入或文件路径 |
"""
    (root / "SKILL.md").write_text(skill_md.strip() + "\n", encoding="utf-8")

    script = (script_body or "").strip()
    if script:
        scripts = root / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        (scripts / "main.py").write_text(script.strip() + "\n", encoding="utf-8")

    return root, True


def update_skill_instructions(name: str, instructions: str, *, mode: str = "append") -> Path:
    """更新已有 Skill 的 SKILL.md 正文（学习闭环：改进 Skill）。"""
    resolved = resolve_skill(name)
    if not resolved:
        raise ValueError(f"未找到 Skill：{name}")
    root, skill_md = resolved
    existing = skill_md.read_text(encoding="utf-8", errors="ignore")
    block = (instructions or "").strip()
    if mode == "replace":
        new_text = block + "\n"
    else:
        new_text = existing.rstrip() + "\n\n## 经验更新\n\n" + block + "\n"
    skill_md.write_text(new_text, encoding="utf-8")
    return root
