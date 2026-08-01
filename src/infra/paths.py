"""路径解析（开发 / PyInstaller 打包）。"""

from __future__ import annotations

import os
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
    """config / dist / resources 等：优先 exe 旁目录，否则使用 bundle 内资源。"""
    external = install_root() / name
    if external.is_dir():
        return external
    return bundle_root() / name


def resolve_config_dir() -> Path:
    return resolve_resource_dir("config")


def app_icon_path() -> Path | None:
    """应用图标（exe / 窗口 / favicon 同源）。"""
    for base in (bundle_root(), install_root()):
        icon = base / "resources" / "windows" / "app-icon.ico"
        if icon.is_file():
            return icon
    return None


def global_config_dir() -> Path:
    """全局配置目录：~/.my-agent/，跨项目共享。"""
    home = Path.home()
    return home / ".my-agent"


def managed_config_dir() -> Path:
    """系统级配置目录：C:\\ProgramData\\my-agent\\，仅管理员可改。"""
    return Path("C:/ProgramData/my-agent")


def project_config_dir(project_root: Path | None = None) -> Path:
    """项目级配置目录：.my-agent/，项目专属。"""
    root = project_root or PROJECT_ROOT
    return root / ".my-agent"


def _refresh_module_paths() -> None:
    global BUNDLE_ROOT, INSTALL_ROOT, PROJECT_ROOT, DATA_DIR, CONFIG_DIR
    global DIST_DIR, LEGACY_WEB_DIR, WEB_DIR, THEMES_DIR
    BUNDLE_ROOT = bundle_root()
    INSTALL_ROOT = install_root()
    PROJECT_ROOT = BUNDLE_ROOT
    DATA_DIR = INSTALL_ROOT / "data"
    CONFIG_DIR = resolve_config_dir()
    # React 构建产物（frontend npm run build → dist/web/）
    DIST_DIR = resolve_resource_dir("dist/web")
    # 旧版 vanilla UI（只读归档，勿当主源码改）
    LEGACY_WEB_DIR = resolve_resource_dir("legacy/web")
    # 兼容旧代码中的 WEB_DIR：指向 React 构建产物
    WEB_DIR = DIST_DIR
    # 主题 JSON：resources/themes
    themes = resolve_resource_dir("resources") / "themes"
    if not themes.is_dir():
        # 兼容尚未迁移的打包布局
        legacy_themes = LEGACY_WEB_DIR / "themes"
        themes = legacy_themes if legacy_themes.is_dir() else themes
    THEMES_DIR = themes


_refresh_module_paths()

BUNDLE_ROOT: Path
INSTALL_ROOT: Path
PROJECT_ROOT: Path
DATA_DIR: Path
CONFIG_DIR: Path
DIST_DIR: Path
LEGACY_WEB_DIR: Path
WEB_DIR: Path
THEMES_DIR: Path
