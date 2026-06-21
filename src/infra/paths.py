"""路径解析（开发 / PyInstaller 打包）。"""

from __future__ import annotations

import sys
from pathlib import Path


def _dev_root() -> Path:
    return Path(__file__).resolve().parents[2]


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def bundle_root() -> Path:
    """只读打包资源根目录（开发时为项目根，PyInstaller 时为 _MEIPASS）。"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return _dev_root()


def install_root() -> Path:
    """可写安装目录（开发时为项目根，打包后为 exe 所在目录）。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return _dev_root()


def resolve_resource_dir(name: str) -> Path:
    """config / web / themes 等：优先 exe 旁目录，否则使用 bundle 内资源。"""
    external = install_root() / name
    if external.is_dir():
        return external
    return bundle_root() / name


def resolve_config_dir() -> Path:
    return resolve_resource_dir("config")


def _refresh_module_paths() -> None:
    global BUNDLE_ROOT, INSTALL_ROOT, PROJECT_ROOT, DATA_DIR, CONFIG_DIR, WEB_DIR, THEMES_DIR
    BUNDLE_ROOT = bundle_root()
    INSTALL_ROOT = install_root()
    PROJECT_ROOT = BUNDLE_ROOT
    DATA_DIR = INSTALL_ROOT / "data"
    CONFIG_DIR = resolve_config_dir()
    WEB_DIR = resolve_resource_dir("web")
    THEMES_DIR = resolve_resource_dir("themes")


_refresh_module_paths()

BUNDLE_ROOT: Path
INSTALL_ROOT: Path
PROJECT_ROOT: Path
DATA_DIR: Path
CONFIG_DIR: Path
WEB_DIR: Path
THEMES_DIR: Path
