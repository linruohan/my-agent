from __future__ import annotations

import platform
import shutil
import sys


def is_fd_installed() -> bool:
    return shutil.which("fd") is not None


def is_rg_installed() -> bool:
    return shutil.which("rg") is not None


def _is_windows() -> bool:
    return sys.platform == "win32"


def install_hint_fd() -> str:
    if _is_windows():
        return (
            "【加速建议】未检测到 fd（快速文件名搜索）。安装后可显著加快 find_files：\n"
            "  · winget:  winget install sharkdp.fd\n"
            "  · scoop:   scoop install fd\n"
            "  · chocolatey: choco install fd\n"
            "  可选 GUI 工具 Everything: winget install voidtools.Everything"
        )
    return (
        "【加速建议】未检测到 fd。安装后可显著加快 find_files：\n"
        "  · macOS:   brew install fd\n"
        "  · Linux:   参见 https://github.com/sharkdp/fd#installation"
    )


def install_hint_rg() -> str:
    if _is_windows():
        return (
            "【加速建议】未检测到 ripgrep (rg)（快速内容搜索）。安装后可显著加快 grep_files：\n"
            "  · winget:  winget install BurntSushi.ripgrep.MSVC\n"
            "  · scoop:   scoop install ripgrep\n"
            "  · chocolatey: choco install ripgrep"
        )
    return (
        "【加速建议】未检测到 ripgrep (rg)。安装后可显著加快 grep_files：\n"
        "  · macOS:   brew install ripgrep\n"
        "  · Linux:   参见 https://github.com/BurntSushi/ripgrep#installation"
    )


def cli_tools_status_text() -> str:
    """返回各 CLI 搜索工具的安装状态与建议。"""
    fd_ok = is_fd_installed()
    rg_ok = is_rg_installed()
    os_name = platform.system()

    lines = [
        f"【本地搜索 CLI 工具状态】系统: {os_name}",
        f"  fd (文件名搜索):       {'✓ 已安装' if fd_ok else '✗ 未安装'}",
        f"  ripgrep/rg (内容搜索): {'✓ 已安装' if rg_ok else '✗ 未安装'}",
        "",
        "当前未安装的工具仍可用内置 Python 引擎搜索，但速度较慢。",
    ]
    if not fd_ok:
        lines.extend(["", install_hint_fd()])
    if not rg_ok:
        lines.extend(["", install_hint_rg()])
    if fd_ok and rg_ok:
        lines.append("\n所有推荐 CLI 工具均已就绪。")
    return "\n".join(lines)


def append_fallback_hint(result: str, engine: str, tool: str) -> str:
    """Python 回退时在结果末尾附加安装建议。"""
    if engine != "python" or not get_fs_option_prefer_cli():
        return result
    if tool == "fd" and not is_fd_installed():
        return result + "\n\n" + install_hint_fd()
    if tool == "rg" and not is_rg_installed():
        return result + "\n\n" + install_hint_rg()
    return result


def get_fs_option_prefer_cli() -> bool:
    try:
        from src.infra.files_config import get_fs_option

        return bool(get_fs_option("prefer_cli", True))
    except Exception:
        return True
