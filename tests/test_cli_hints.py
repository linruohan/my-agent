from __future__ import annotations

from unittest.mock import patch

from src.tools.cli_hints import (
    append_fallback_hint,
    cli_tools_status_text,
    install_hint_fd,
    install_hint_rg,
)


def test_install_hint_fd_mentions_winget():
    hint = install_hint_fd()
    assert "winget" in hint
    assert "fd" in hint


def test_install_hint_rg_mentions_winget():
    hint = install_hint_rg()
    assert "winget" in hint
    assert "ripgrep" in hint


def test_cli_tools_status_when_missing():
    with patch("src.tools.cli_hints.is_fd_installed", return_value=False), patch(
        "src.tools.cli_hints.is_rg_installed", return_value=False
    ):
        text = cli_tools_status_text()
    assert "未安装" in text
    assert "winget" in text


def test_cli_tools_status_when_all_installed():
    with patch("src.tools.cli_hints.is_fd_installed", return_value=True), patch(
        "src.tools.cli_hints.is_rg_installed", return_value=True
    ):
        text = cli_tools_status_text()
    assert "已安装" in text
    assert "均已就绪" in text


def test_append_fallback_hint_on_python_engine():
    with patch("src.tools.cli_hints.is_fd_installed", return_value=False), patch(
        "src.tools.cli_hints.get_fs_option_prefer_cli", return_value=True
    ):
        out = append_fallback_hint("搜索结果", "python", "fd")
    assert "加速建议" in out
    assert "winget" in out


def test_append_fallback_hint_skips_when_cli_used():
    out = append_fallback_hint("搜索结果", "fd", "fd")
    assert out == "搜索结果"
