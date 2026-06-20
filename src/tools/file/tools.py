"""LangChain @tool 装饰器：本地文件相关工具。"""

from __future__ import annotations

from langchain_core.tools import tool

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
from src.tools.file.search import (
    find_files_impl,
    grep_files_impl,
    list_directory_impl,
    read_local_file_impl,
)


@tool
def search_tools_status() -> str:
    """查看本地文件搜索 CLI 工具（fd、ripgrep）的安装状态，并给出安装建议。"""
    return cli_tools_status_text()


@tool
def find_files(
    pattern: str,
    root: str = "",
    file_type: str = "any",
    max_results: int = 50,
) -> str:
    """按文件名或通配符查找本地文件/文件夹（类似 Everything / fd）。

    Args:
        pattern: 文件名模式，支持通配符如 *.py、*config*、README.md
        root: 搜索根目录，留空则使用默认允许目录（用户主目录等）
        file_type: any（默认）/ file / dir
        max_results: 最大返回条数，默认 50
    """
    return find_files_impl(pattern, root, file_type, max_results)


@tool
def grep_files(
    pattern: str,
    root: str = "",
    glob: str = "*",
    max_results: int = 30,
    context_lines: int = 2,
) -> str:
    """在本地文件内容中搜索文本或正则表达式（类似 ripgrep / grep）。

    Args:
        pattern: 搜索词或正则表达式
        root: 搜索根目录，留空则使用默认允许目录
        glob: 文件名过滤，如 *.py、*.txt，默认 * 表示所有文本类文件
        max_results: 最大匹配条数
        context_lines: 匹配行前后显示的上下文行数
    """
    return grep_files_impl(pattern, root, glob, max_results, context_lines)


@tool
def list_directory(path: str = "", max_entries: int = 100) -> str:
    """列出本地目录下的文件和子文件夹。

    Args:
        path: 目录路径，留空则列出默认根目录
        max_entries: 最大显示条目数
    """
    return list_directory_impl(path, max_entries)


@tool
def read_local_file(path: str, max_lines: int = 200, offset: int = 1) -> str:
    """读取本地文本文件的内容（需在允许目录范围内）。

    Args:
        path: 文件绝对或相对路径
        max_lines: 最多读取行数，默认 200
        offset: 起始行号（从 1 开始）
    """
    return read_local_file_impl(path, max_lines, offset)


@tool
def create_file(path: str, content: str = "", overwrite: bool = False) -> str:
    """创建新文件。敏感操作（overwrite=True 时覆盖已有文件）。

    Args:
        path: 文件路径
        content: 初始内容
        overwrite: 是否覆盖已存在文件
    """
    return create_file_impl(path, content, overwrite)


@tool
def write_local_file(path: str, content: str, mode: str = "overwrite") -> str:
    """写入或追加文件内容。敏感操作。

    Args:
        path: 文件路径
        content: 写入内容
        mode: overwrite（覆盖）或 append（追加）
    """
    return write_local_file_impl(path, content, mode)


@tool
def delete_path(path: str, permanent: bool = False) -> str:
    """删除文件或目录。默认移入 .trash 回收站；permanent=True 永久删除。敏感操作。

    Args:
        path: 目标路径
        permanent: 是否永久删除（不可恢复）
    """
    return delete_path_impl(path, permanent)


@tool
def copy_path(source: str, destination: str) -> str:
    """复制文件或目录到新位置。敏感操作。

    Args:
        source: 源路径
        destination: 目标路径（不可已存在）
    """
    return copy_path_impl(source, destination)


@tool
def move_path(source: str, destination: str) -> str:
    """移动/剪切文件或目录。敏感操作。

    Args:
        source: 源路径
        destination: 目标路径
    """
    return move_path_impl(source, destination)


@tool
def rename_path(path: str, new_name: str) -> str:
    """重命名文件或目录（同目录下改名称）。敏感操作。

    Args:
        path: 原路径
        new_name: 新文件名（不含目录部分）
    """
    return rename_path_impl(path, new_name)


@tool
def create_directory(path: str, parents: bool = True) -> str:
    """创建文件夹。

    Args:
        path: 目录路径
        parents: 是否递归创建父目录
    """
    return create_directory_impl(path, parents)


@tool
def remove_directory(path: str, recursive: bool = False) -> str:
    """删除目录。recursive=True 递归删除非空目录。敏感操作。

    Args:
        path: 目录路径
        recursive: 是否递归删除
    """
    return remove_directory_impl(path, recursive)


@tool
def get_path_info(path: str) -> str:
    """查看文件/目录属性：大小、时间戳、只读、扩展名、绝对路径等。

    Args:
        path: 文件或目录路径
    """
    return get_path_info_impl(path)


@tool
def set_file_attributes(path: str, readonly: bool | None = None, hidden: bool | None = None) -> str:
    """设置文件属性（只读、隐藏）。敏感操作。

    Args:
        path: 文件路径
        readonly: True 设为只读，False 取消只读，None 不修改
        hidden: True 隐藏（仅 Windows），False 取消隐藏，None 不修改
    """
    return set_file_attributes_impl(path, readonly, hidden)


@tool
def get_disk_usage(path: str = "") -> str:
    """查看磁盘空间占用。

    Args:
        path: 目录路径，留空则查看默认根目录所在磁盘
    """
    return get_disk_usage_impl(path)


@tool
def read_file_bytes(path: str, offset: int = 0, length: int = 4096) -> str:
    """按字节偏移读取文件片段（Seek 模式），适合大文件或二进制。

    Args:
        path: 文件路径
        offset: 起始字节偏移
        length: 读取字节数
    """
    return read_file_bytes_impl(path, offset, length)


@tool
def stream_read_file(path: str, chunk_lines: int = 100, start_line: int = 1) -> str:
    """流式分块读取文本文件，不一次性加载到内存。

    Args:
        path: 文件路径
        chunk_lines: 每块行数
        start_line: 起始行号
    """
    return stream_read_file_impl(path, chunk_lines, start_line)


@tool
def create_symlink(target: str, link_path: str, is_dir: bool = False) -> str:
    """创建符号链接（软链接）。敏感操作。

    Args:
        target: 链接目标路径
        link_path: 链接文件路径
        is_dir: 目标是否为目录
    """
    return create_symlink_impl(target, link_path, is_dir)


@tool
def write_local_file_locked(path: str, content: str, mode: str = "overwrite") -> str:
    """带文件锁的写入，适合并发场景。敏感操作。

    Args:
        path: 文件路径
        content: 内容
        mode: overwrite 或 append
    """
    return write_local_file_locked_impl(path, content, mode)


FILE_TOOLS = [
    search_tools_status,
    find_files,
    grep_files,
    list_directory,
    read_local_file,
    create_file,
    write_local_file,
    write_local_file_locked,
    delete_path,
    copy_path,
    move_path,
    rename_path,
    create_directory,
    remove_directory,
    get_path_info,
    set_file_attributes,
    get_disk_usage,
    read_file_bytes,
    stream_read_file,
    create_symlink,
]
