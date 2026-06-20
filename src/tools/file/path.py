from __future__ import annotations

import os
import stat
import sys
from datetime import datetime
from pathlib import Path

from src.infra.files_config import get_search_roots
from src.infra.paths import DATA_DIR


class PathNotAllowedError(PermissionError):
    pass


def fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def trash_directory() -> Path:
    d = DATA_DIR / "workspace" / ".trash"
    d.mkdir(parents=True, exist_ok=True)
    return d


def assert_allowed(path: Path) -> None:
    resolved = path.resolve()
    for root in get_search_roots():
        try:
            resolved.relative_to(root.resolve())
            return
        except ValueError:
            continue
    allowed = ", ".join(str(r) for r in get_search_roots())
    raise PathNotAllowedError(f"路径不在允许范围内: {path}\n允许目录: {allowed}")


def resolve_path(path: str, *, must_exist: bool = True) -> Path:
    p = Path(path.strip()).expanduser()
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    else:
        p = p.resolve()
    if must_exist:
        assert_allowed(p)
        if not p.exists():
            raise FileNotFoundError(f"路径不存在: {p}")
    else:
        assert_allowed(p if p.exists() else p.parent)
    return p


def resolve_path_for_create(path: str) -> Path:
    """解析待创建路径，校验父目录或目标目录在允许范围内。"""
    p = Path(path.strip()).expanduser()
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    else:
        p = p.resolve()
    check = p.parent if p.name else p
    assert_allowed(check)
    return p


def format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:,} {unit}"
        n //= 1024
    return f"{n:,} TB"


def is_windows() -> bool:
    return sys.platform == "win32"


def set_hidden(path: Path, hidden: bool) -> None:
    if not is_windows():
        return
    import subprocess

    flag = "+H" if hidden else "-H"
    subprocess.run(["attrib", flag, str(path)], check=False, capture_output=True)


def set_readonly_flag(path: Path, readonly: bool) -> None:
    mode = path.stat().st_mode
    if readonly:
        path.chmod(mode & ~stat.S_IWRITE)
    else:
        path.chmod(mode | stat.S_IWRITE)
