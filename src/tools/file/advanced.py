from __future__ import annotations

import contextlib
import os
from pathlib import Path

from src.infra.files_config import get_fs_option
from src.tools.file.ops import write_local_file_impl
from src.tools.file.path import assert_allowed, resolve_path, resolve_path_for_create


def read_file_bytes_impl(path: str, offset: int = 0, length: int = 4096) -> str:
    """按字节偏移读取（Seek 模式），适用于大文件或二进制片段。"""
    p = resolve_path(path)
    if not p.is_file():
        raise IsADirectoryError(f"不是文件: {p}")
    max_size = int(get_fs_option("max_file_size_mb", 5)) * 1024 * 1024
    file_size = p.stat().st_size
    if offset < 0 or offset >= file_size:
        raise ValueError(f"offset 超出范围: 0-{file_size - 1}")
    length = min(length, max_size, file_size - offset)
    with p.open("rb") as f:
        f.seek(offset)
        data = f.read(length)
    preview = data[:200]
    try:
        text_preview = preview.decode("utf-8")
        display = repr(text_preview)
    except UnicodeDecodeError:
        display = f"<binary {len(data)} bytes> hex={preview[:32].hex()}..."
    return (
        f"【字节读取】{p}\n"
        f"  偏移: {offset} | 读取: {len(data)} 字节 | 文件总大小: {file_size:,} 字节\n"
        f"  预览: {display}"
    )


def stream_read_file_impl(path: str, chunk_lines: int = 100, start_line: int = 1) -> str:
    """流式按块读取文本文件（不一次性加载全部内容）。"""
    p = resolve_path(path)
    if not p.is_file():
        raise IsADirectoryError(f"不是文件: {p}")
    chunk_lines = min(chunk_lines, 500)
    lines_out: list[str] = []
    total = 0
    with p.open(encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f, 1):
            total = i
            if i < start_line:
                continue
            if len(lines_out) >= chunk_lines:
                break
            lines_out.append(f"{i:5}| {line.rstrip()}")
    header = (
        f"【流式读取】{p} | 块大小 {chunk_lines} 行 | 起始于第 {start_line} 行\n"
        f"  已扫描至第 {total} 行\n"
    )
    if not lines_out:
        return header + "（无内容或 start_line 超出范围）"
    remaining = total - (start_line + len(lines_out) - 1)
    body = "\n".join(lines_out)
    if remaining > 0:
        body += f"\n\n… 后续至少还有内容，可用 start_line={start_line + len(lines_out)} 继续"
    return header + body


def create_symlink_impl(target: str, link_path: str, is_dir: bool = False) -> str:
    """创建符号链接（软链接）。"""
    link = resolve_path_for_create(link_path)
    tgt = Path(target.strip()).expanduser()
    if not tgt.is_absolute():
        tgt = (link.parent / tgt).resolve()
    assert_allowed(tgt)
    if link.exists():
        raise FileExistsError(f"链接路径已存在: {link}")
    link.parent.mkdir(parents=True, exist_ok=True)
    if is_dir:
        os.symlink(tgt, link, target_is_directory=True)
    else:
        os.symlink(tgt, link)
    return f"已创建符号链接: {link} → {tgt}"


@contextlib.contextmanager
def _file_write_lock(path: Path):
    """简易文件锁，防止并发写入冲突。"""
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = None
    try:
        lock_fd = lock_path.open("w")
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        if lock_fd:
            lock_fd.close()
        if lock_path.exists():
            lock_path.unlink(missing_ok=True)


def write_local_file_locked_impl(path: str, content: str, mode: str = "overwrite") -> str:
    """带文件锁的写入（多进程安全）。"""
    p = (
        resolve_path_for_create(path)
        if mode != "append" or not Path(path).exists()
        else resolve_path(path)
    )
    p.parent.mkdir(parents=True, exist_ok=True)
    with _file_write_lock(p):
        return write_local_file_impl(path, content, mode)
