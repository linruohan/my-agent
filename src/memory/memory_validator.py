"""记忆验证器：格式校验、老化判断、主动验证。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

MEMORY_TYPES = ["user", "feedback", "project", "reference"]


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


def validate_memory_format(file_path: Path) -> tuple[bool, list[str]]:
    """校验记忆文件格式是否符合规范。"""
    errors = []

    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return False, ["无法读取文件"]

    if not text:
        return False, ["文件为空"]

    frontmatter, body = _parse_frontmatter(text)

    if not frontmatter:
        errors.append("缺少 frontmatter")
    else:
        if "type" not in frontmatter:
            errors.append("frontmatter 缺少 type 字段")
        else:
            memory_type = frontmatter["type"]
            if memory_type not in MEMORY_TYPES:
                errors.append(f"type 无效：{memory_type}，必须是 {MEMORY_TYPES}")

        if "name" not in frontmatter or not str(frontmatter.get("name", "")).strip():
            errors.append("frontmatter 缺少 name 字段")

        if "description" not in frontmatter or not str(frontmatter.get("description", "")).strip():
            errors.append("frontmatter 缺少 description 字段")

        if "created" in frontmatter:
            created = frontmatter["created"]
            try:
                datetime.strptime(created, "%Y-%m-%d")
            except ValueError:
                errors.append(f"created 格式无效：{created}，应为 YYYY-MM-DD")

        if "updated" in frontmatter:
            updated = frontmatter["updated"]
            try:
                datetime.strptime(updated, "%Y-%m-%d")
            except ValueError:
                errors.append(f"updated 格式无效：{updated}，应为 YYYY-MM-DD")

        if "tags" in frontmatter and not isinstance(frontmatter["tags"], list):
            errors.append("tags 必须是数组")

    if not body:
        errors.append("记忆正文为空")
    else:
        memory_type = frontmatter.get("type", "")
        if memory_type in ["feedback", "project"]:
            if "**Why:**" not in body:
                errors.append(f"{memory_type} 类型记忆必须包含 Why 部分")
            if "**How to apply:**" not in body:
                errors.append(f"{memory_type} 类型记忆必须包含 How to apply 部分")

    return len(errors) == 0, errors


def is_memory_stale(file_path: Path, stale_days: int = 2) -> bool:
    """判断记忆是否过期。"""
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return False

    frontmatter, _ = _parse_frontmatter(text)
    updated = frontmatter.get("updated", "")

    if not updated:
        return False

    try:
        updated_date = datetime.strptime(updated, "%Y-%m-%d")
        delta = datetime.now() - updated_date
        return delta.days >= stale_days
    except ValueError:
        return False


def get_stale_days(file_path: Path) -> int | None:
    """获取记忆过期天数。"""
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return None

    frontmatter, _ = _parse_frontmatter(text)
    updated = frontmatter.get("updated", "")

    if not updated:
        return None

    try:
        updated_date = datetime.strptime(updated, "%Y-%m-%d")
        delta = datetime.now() - updated_date
        return delta.days
    except ValueError:
        return None


def contains_file_path(content: str) -> list[str]:
    """检测记忆内容中是否包含文件路径。"""
    patterns = [
        r"[a-zA-Z]:\\[^\s\"']*",
        r"/[^\s\"']+",
        r"\.\.?/[^\s\"']+",
    ]
    paths = []
    for pattern in patterns:
        matches = re.findall(pattern, content)
        paths.extend(matches)
    return paths


def contains_function_name(content: str) -> list[str]:
    """检测记忆内容中是否包含函数名。"""
    patterns = [
        r"\bdef\s+(\w+)\(",
        r"\bfunction\s+(\w+)\(",
        r"\b(\w+)\s*=\s*function\s*\(",
    ]
    functions = []
    for pattern in patterns:
        matches = re.findall(pattern, content)
        functions.extend(matches)
    return functions


def contains_flag_name(content: str) -> list[str]:
    """检测记忆内容中是否包含 flag 名。"""
    patterns = [
        r"\b([A-Z_]+)\s*=\s*(True|False|1|0)",
        r"\b(--\w+)",
        r"\b(-\w)",
    ]
    flags = []
    for pattern in patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            if isinstance(match, tuple):
                flags.append(match[0])
            else:
                flags.append(match)
    return flags


def build_verification_prompt(content: str) -> str:
    """构建主动验证提示词，要求模型在使用记忆前验证信息。"""
    paths = contains_file_path(content)
    functions = contains_function_name(content)
    flags = contains_flag_name(content)

    if not paths and not functions and not flags:
        return ""

    parts = ["使用以下记忆前，请先验证："]

    if paths:
        parts.append(f"- 文件路径：{', '.join(paths)}（检查文件是否存在）")
    if functions:
        parts.append(f"- 函数名：{', '.join(functions)}（grep 确认是否存在）")
    if flags:
        parts.append(f"- 配置项：{', '.join(flags)}（确认当前值）")

    return "\n".join(parts)