"""系统级工具 API：剪贴板、本地路径。"""

from __future__ import annotations

from src.ui.api.base import ApiBase
from src.ui.clipboard import copy_to_clipboard as sys_copy_to_clipboard
from src.ui.open_local import check_local_paths as sys_check_local_paths
from src.ui.open_local import open_local_path as sys_open_local_path


class SystemApiMixin(ApiBase):
    """剪贴板与本地文件打开。"""

    def copy_to_clipboard(self, text: str) -> bool:
        return sys_copy_to_clipboard(text)

    def open_local_path(self, path: str) -> dict:
        return sys_open_local_path(path)

    def check_local_paths(self, paths: list[str]) -> dict[str, bool]:
        return sys_check_local_paths(paths)
