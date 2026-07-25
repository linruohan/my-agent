"""系统文件对话框（主线程安全封装）。"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webview.window import Window


def create_file_dialog_safe(
    window: Window,
    dialog_type: int,
    *,
    directory: str = "",
    allow_multiple: bool = False,
    save_filename: str = "",
    file_types: Sequence[str] = (),
) -> Sequence[str] | None:
    """在 GUI 主线程打开系统文件对话框。

    pywebview 暴露给 JS 的 API 在后台线程执行；在 Windows 上直接调用
    ``window.create_file_dialog`` 会与 WinForms UI 线程死锁，表现为打开/保存对话框卡住。
    """
    result: list[Sequence[str] | None] = [None]

    def run_dialog() -> None:
        result[0] = window.create_file_dialog(
            dialog_type,
            directory=directory,
            allow_multiple=allow_multiple,
            save_filename=save_filename,
            file_types=file_types,
        )

    if sys.platform == "win32":
        try:
            from webview.platforms import winforms

            browser = winforms.BrowserView.instances.get(window.uid)
            if browser is not None and browser.InvokeRequired:
                from System import Func, Type  # type: ignore[import-untyped]

                browser.Invoke(Func[Type](run_dialog))
                return result[0]
        except Exception:
            from loguru import logger

            logger.debug("文件对话框失败", exc_info=True)

    run_dialog()
    return result[0]
