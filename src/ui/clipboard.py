"""系统剪贴板写入（pywebview / WebView2 下 JS clipboard 可能不可用）。"""

from __future__ import annotations

import sys


def copy_to_clipboard(text: str) -> bool:
    if not text:
        return False
    if sys.platform == "win32":
        try:
            import win32clipboard  # type: ignore[import-untyped]

            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
            return True
        except Exception:
            from loguru import logger

            logger.debug("剪贴板操作失败", exc_info=True)
        try:
            import subprocess

            proc = subprocess.run(
                ["clip"],
                input=text,
                text=True,
                encoding="utf-8",
                check=False,
                capture_output=True,
            )
            if proc.returncode == 0:
                return True
        except Exception:
            from loguru import logger

            logger.debug("剪贴板操作失败", exc_info=True)
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return True
    except Exception:
        return False
