"""file_dialog 主线程封装测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import webview

from src.ui.file_dialog import create_file_dialog_safe


def test_create_file_dialog_safe_direct_when_no_invoke_required():
    window = MagicMock()
    window.uid = "test"
    window.create_file_dialog.return_value = ("C:\\a.txt",)

    with patch("src.ui.file_dialog.sys.platform", "win32"):
        with patch("webview.platforms.winforms.BrowserView.instances", {"test": MagicMock(InvokeRequired=False)}):
            result = create_file_dialog_safe(window, webview.OPEN_DIALOG)

    assert result == ("C:\\a.txt",)
    window.create_file_dialog.assert_called_once()


def test_create_file_dialog_safe_marshals_to_ui_thread():
    window = MagicMock()
    window.uid = "test"
    window.create_file_dialog.return_value = ("C:\\b.txt",)

    browser = MagicMock()
    browser.InvokeRequired = True

    def invoke(func):
        func()

    browser.Invoke.side_effect = invoke

    with patch("src.ui.file_dialog.sys.platform", "win32"):
        with patch("webview.platforms.winforms.BrowserView.instances", {"test": browser}):
            result = create_file_dialog_safe(window, webview.FOLDER_DIALOG)

    assert result == ("C:\\b.txt",)
    browser.Invoke.assert_called_once()
    window.create_file_dialog.assert_called_once()
