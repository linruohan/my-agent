"""本地文件工具包。

目录结构约定（后续同类工具参照此模式）：
  path.py      — 路径校验与沙箱
  hints.py     — CLI 工具安装提示
  search.py    — 查找 / grep / 读取 / 列表
  ops.py       — 增删改查、复制、移动
  meta.py      — 属性与磁盘信息
  advanced.py  — Seek、流式读、文件锁、软链接
  tools.py     — LangChain @tool 装饰器与 FILE_TOOLS 列表
"""

from src.tools.file.advanced import (
    create_symlink_impl,
    read_file_bytes_impl,
    stream_read_file_impl,
    write_local_file_locked_impl,
)
from src.tools.file.hints import cli_tools_status_text
from src.tools.file.meta import get_disk_usage_impl, get_path_info_impl, set_file_attributes_impl
from src.tools.file.ops import (
    copy_path_impl,
    create_directory_impl,
    create_file_impl,
    delete_path_impl,
    move_path_impl,
    remove_directory_impl,
    rename_path_impl,
    write_local_file_impl,
)
from src.tools.file.path import PathNotAllowedError, assert_allowed, resolve_path
from src.tools.file.search import (
    find_files_impl,
    grep_files_impl,
    list_directory_impl,
    read_local_file_impl,
)
from src.tools.file.tools import FILE_TOOLS

__all__ = [
    "FILE_TOOLS",
    "PathNotAllowedError",
    "assert_allowed",
    "cli_tools_status_text",
    "copy_path_impl",
    "create_directory_impl",
    "create_file_impl",
    "create_symlink_impl",
    "delete_path_impl",
    "find_files_impl",
    "get_disk_usage_impl",
    "get_path_info_impl",
    "grep_files_impl",
    "list_directory_impl",
    "move_path_impl",
    "read_file_bytes_impl",
    "read_local_file_impl",
    "remove_directory_impl",
    "rename_path_impl",
    "resolve_path",
    "set_file_attributes_impl",
    "stream_read_file_impl",
    "write_local_file_impl",
    "write_local_file_locked_impl",
]
