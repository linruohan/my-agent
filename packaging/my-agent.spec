# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Windows exe 打包。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
root = Path(SPECPATH).resolve().parent

icon_path = root / "resources" / "windows" / "app-icon.ico"

datas = [
    (str(root / "config"), "config"),
    (str(root / "web"), "web"),
    (str(root / "themes"), "themes"),
    (str(root / "resources"), "resources"),
]

binaries: list[tuple[str, str, str]] = []
hiddenimports = [
    "main",
    "webview",
    "sqlite3",
    "multiprocessing",
    "keyring.backends.Windows",
    "win32timezone",
    "win32api",
    "win32con",
    "pythoncom",
    "pywintypes",
]

# LangChain / LangGraph 动态导入较多
hiddenimports += collect_submodules("langchain")
hiddenimports += collect_submodules("langchain_core")
hiddenimports += collect_submodules("langchain_community")
hiddenimports += collect_submodules("langchain_openai")
hiddenimports += collect_submodules("langchain_text_splitters")
hiddenimports += collect_submodules("langgraph")
hiddenimports += collect_submodules("langgraph_checkpoint_sqlite")

# Windows 平台能力
if sys.platform == "win32":
    for pkg in (
        "winrt",
        "winrt.runtime",
        "winrt.windows.media.speechrecognition",
        "winrt.windows.media.ocr",
        "winrt.windows.graphics.imaging",
        "winrt.windows.storage",
        "winrt.windows.storage.streams",
        "winrt.windows.globalization",
        "winrt.windows.foundation",
    ):
        hiddenimports += collect_submodules(pkg)

# 部分依赖携带非 Python 数据文件
for pkg in ("fastembed", "faiss", "yaml"):
    try:
        _datas, _binaries, _hidden = collect_all(pkg)
        datas += _datas
        binaries += _binaries
        hiddenimports += _hidden
    except Exception:
        pass

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "paddle",
        "paddleocr",
        "matplotlib",
        "tkinter",
        "IPython",
        "jupyter",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="my-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.is_file() else None,
)
