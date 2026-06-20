from __future__ import annotations

import os
import shutil
import stat

from src.tools.file.path import (
    fmt_time,
    format_bytes,
    is_windows,
    resolve_path,
    set_hidden,
    set_readonly_flag,
)


def get_path_info_impl(path: str) -> str:
    p = resolve_path(path)
    st = p.stat()
    lines = [
        f"【路径信息】{p}",
        f"  类型: {'目录' if p.is_dir() else '文件' if p.is_file() else '其他'}",
        f"  绝对路径: {p.resolve()}",
        f"  父目录: {p.parent}",
        f"  大小: {format_bytes(st.st_size)}",
        f"  创建时间: {fmt_time(st.st_ctime)}",
        f"  修改时间: {fmt_time(st.st_mtime)}",
        f"  访问时间: {fmt_time(st.st_atime)}",
    ]
    if p.is_file():
        lines.append(f"  扩展名: {p.suffix or '(无)'}")
    if p.is_symlink():
        lines.append(f"  符号链接目标: {os.readlink(p)}")
    readonly = not (st.st_mode & stat.S_IWRITE)
    lines.append(f"  只读: {'是' if readonly else '否'}")
    if is_windows():
        try:
            import subprocess

            proc = subprocess.run(
                ["attrib", str(p)], capture_output=True, text=True, creationflags=0x08000000
            )
            hidden = "H" in (proc.stdout or "")
            lines.append(f"  隐藏: {'是' if hidden else '否'}")
        except OSError:
            lines.append("  隐藏: (无法检测)")
    return "\n".join(lines)


def set_file_attributes_impl(
    path: str,
    readonly: bool | None = None,
    hidden: bool | None = None,
) -> str:
    p = resolve_path(path)
    changes: list[str] = []
    if readonly is not None:
        set_readonly_flag(p, readonly)
        changes.append(f"只读={'开启' if readonly else '关闭'}")
    if hidden is not None and is_windows():
        set_hidden(p, hidden)
        changes.append(f"隐藏={'开启' if hidden else '关闭'}")
    elif hidden is not None:
        changes.append("隐藏属性仅 Windows 支持，已跳过")
    if not changes:
        return "未指定要修改的属性。"
    return f"已更新 {p}: " + "，".join(changes)


def get_disk_usage_impl(path: str = "") -> str:
    if path:
        p = resolve_path(path)
        target = str(p if p.is_dir() else p.parent)
    else:
        from src.infra.files_config import get_search_roots

        target = str(get_search_roots()[0])
    usage = shutil.disk_usage(target)
    total, used, free = usage
    pct = used / total * 100 if total else 0
    return (
        f"【磁盘占用】{target}\n"
        f"  总容量: {format_bytes(total)}\n"
        f"  已用:   {format_bytes(used)} ({pct:.1f}%)\n"
        f"  可用:   {format_bytes(free)}"
    )
