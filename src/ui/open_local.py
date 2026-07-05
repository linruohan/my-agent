"""用系统默认应用打开本地文件或目录，支持指定行号。"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from loguru import logger

_TRAILING_PUNCT_RE = re.compile(r'[.,;，。:!?\u3001\u3002)\]}>]+$', re.UNICODE)


def clean_local_path(raw: str) -> str:
    path = (raw or "").strip().strip("\"'`")
    while path:
        if _TRAILING_PUNCT_RE.search(path) and not path.endswith("\\"):
            ext = re.search(r"(\.[A-Za-z0-9]{1,8})$", path)
            if ext and path.endswith(ext.group(1)):
                break
            path = _TRAILING_PUNCT_RE.sub("", path)
            continue
        break
    return path


def resolve_local_path(raw: str) -> dict[str, Any]:
    """解析并检查本地路径是否存在。"""
    cleaned = clean_local_path(raw)
    if not cleaned:
        return {"exists": False, "path": ""}

    try:
        target = Path(cleaned).expanduser().resolve()
    except OSError:
        return {"exists": False, "path": cleaned}

    return {"exists": target.exists(), "path": str(target)}


def local_path_exists(raw: str) -> bool:
    return bool(resolve_local_path(raw)["exists"])


def check_local_paths(raw_paths: list[str]) -> dict[str, bool]:
    """批量检查路径是否存在，键为原始传入字符串。"""
    result: dict[str, bool] = {}
    for raw in raw_paths:
        if raw in result:
            continue
        result[raw] = local_path_exists(raw)
    return result


def _parse_path_with_line(raw: str) -> tuple[str, int | None]:
    """解析路径和行号，支持 path:line 格式。"""
    cleaned = clean_local_path(raw)
    if not cleaned:
        return "", None

    last_colon = cleaned.rfind(":")
    if last_colon > 0:
        after = cleaned[last_colon + 1:]
        if after.isdigit():
            line_no = int(after)
            path_part = cleaned[:last_colon]
            if path_part and (path_part.count(":") <= 1 or path_part.startswith("//")):
                return path_part, line_no
    return cleaned, None


def open_local_path(raw: str) -> dict[str, Any]:
    """打开本地路径；使用系统默认应用打开。"""
    path_str, line_no = _parse_path_with_line(raw)
    if not path_str:
        return {"ok": False, "error": "路径为空"}

    try:
        target = Path(path_str).expanduser().resolve()
    except OSError:
        return {"ok": False, "error": f"路径无效: {path_str}"}

    if not target.exists():
        return {"ok": False, "error": f"路径不存在: {target}"}

    try:
        if sys.platform == "win32":
            os.startfile(str(target))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.run(["open", str(target)], check=True)
        else:
            subprocess.run(["xdg-open", str(target)], check=True)
    except Exception as exc:
        logger.warning("打开本地路径失败 {}: {}", target, exc)
        return {"ok": False, "error": str(exc)}

    return {"ok": True, "path": str(target), "line": line_no}
