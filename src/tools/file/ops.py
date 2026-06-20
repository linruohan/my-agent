from __future__ import annotations

import shutil
import time
from pathlib import Path

from src.tools.file.path import (
    assert_allowed,
    resolve_path,
    resolve_path_for_create,
    trash_directory,
)


def create_file_impl(path: str, content: str = "", overwrite: bool = False) -> str:
    p = resolve_path_for_create(path)
    if p.exists() and not overwrite:
        raise FileExistsError(f"文件已存在: {p}（设置 overwrite=True 可覆盖）")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"已创建文件: {p}（{len(content.encode('utf-8')):,} 字节）"


def write_local_file_impl(path: str, content: str, mode: str = "overwrite") -> str:
    """写入文件。mode: overwrite（覆盖）| append（追加）。"""
    raw = Path(path.strip()).expanduser()
    p = (Path.cwd() / raw).resolve() if not raw.is_absolute() else raw.resolve()
    if mode == "append" and p.exists():
        assert_allowed(p)
    else:
        p = resolve_path_for_create(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if mode == "append":
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
            f.flush()
        action = "追加"
    else:
        p.write_text(content, encoding="utf-8")
        action = "覆盖写入"
    return f"已{action}: {p}（+{len(content.encode('utf-8')):,} 字节）"


def create_directory_impl(path: str, parents: bool = True) -> str:
    p = resolve_path_for_create(path)
    p.mkdir(parents=parents, exist_ok=True)
    return f"已创建目录: {p}"


def delete_path_impl(path: str, permanent: bool = False) -> str:
    p = resolve_path(path)
    if permanent:
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return f"已永久删除: {p}"
    trash = trash_directory()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dest = trash / f"{stamp}_{p.name}"
    counter = 0
    while dest.exists():
        counter += 1
        dest = trash / f"{stamp}_{counter}_{p.name}"
    shutil.move(str(p), str(dest))
    return f"已移入回收站 (.trash): {p} → {dest}"


def remove_directory_impl(path: str, recursive: bool = False) -> str:
    p = resolve_path(path)
    if not p.is_dir():
        raise NotADirectoryError(f"不是目录: {p}")
    if recursive:
        shutil.rmtree(p)
        return f"已递归删除目录: {p}"
    p.rmdir()
    return f"已删除空目录: {p}"


def copy_path_impl(source: str, destination: str) -> str:
    src = resolve_path(source)
    dst = resolve_path_for_create(destination)
    if dst.exists():
        raise FileExistsError(f"目标已存在: {dst}")
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return f"已复制: {src} → {dst}"


def move_path_impl(source: str, destination: str) -> str:
    src = resolve_path(source)
    dst = resolve_path_for_create(destination)
    if dst.exists():
        raise FileExistsError(f"目标已存在: {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return f"已移动: {src} → {dst}"


def rename_path_impl(path: str, new_name: str) -> str:
    p = resolve_path(path)
    new_path = p.parent / new_name.strip()
    assert_allowed(new_path)
    if new_path.exists():
        raise FileExistsError(f"目标已存在: {new_path}")
    p.rename(new_path)
    return f"已重命名: {p.name} → {new_name}（{new_path}）"
