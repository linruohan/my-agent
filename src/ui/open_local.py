"""用系统默认应用打开本地文件或目录。"""

from __future__ import annotations

import os
import re
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


def open_local_path(raw: str) -> dict[str, Any]:
    """打开本地路径；Windows 使用默认关联应用。"""
    cleaned = clean_local_path(raw)
    if not cleaned:
        return {"ok": False, "error": "路径为空"}

    resolved = resolve_local_path(cleaned)
    target = Path(resolved["path"]) if resolved["path"] else Path(cleaned)
    if not resolved["exists"]:
        return {"ok": False, "error": f"路径不存在: {target}"}

    try:
        if sys.platform == "win32":
            os.startfile(str(target))  # noqa: S606
        elif sys.platform == "darwin":
            import subprocess

            subprocess.run(["open", str(target)], check=True)
        else:
            import subprocess

            subprocess.run(["xdg-open", str(target)], check=True)
    except Exception as exc:
        logger.warning("打开本地路径失败 {}: {}", target, exc)
        return {"ok": False, "error": str(exc)}

    return {"ok": True, "path": str(target)}
