"""附件与知识库文件选择。"""

from __future__ import annotations

from typing import Any

import webview

from src.ui.file_dialog import create_file_dialog_safe


class FilesMixin:
    """附件与知识库文件选择。"""

    def pick_input_image(self) -> dict[str, Any]:
        window = self._get_window()
        if window is None:
            return {"ok": False, "paths": []}
        file_types = ("图片 (*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif)", "All files (*.*)")
        try:
            paths = create_file_dialog_safe(
                window,
                webview.OPEN_DIALOG,
                allow_multiple=True,
                file_types=file_types,
            )
            return {"ok": True, "paths": list(paths or [])}
        except Exception as exc:
            return {"ok": False, "paths": [], "error": str(exc)}

    def pick_input_file(self) -> dict[str, Any]:
        window = self._get_window()
        if window is None:
            return {"ok": False, "paths": []}
        try:
            paths = create_file_dialog_safe(window, webview.OPEN_DIALOG, allow_multiple=True)
            return {"ok": True, "paths": list(paths or [])}
        except Exception as exc:
            return {"ok": False, "paths": [], "error": str(exc)}
