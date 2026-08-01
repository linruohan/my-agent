"""路径解析（开发 / PyInstaller 打包）。"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _reload_paths():
    import src.infra.paths as paths

    importlib.reload(paths)
    return paths


def test_dev_layout():
    paths = _reload_paths()
    root = paths._dev_root()
    assert paths.bundle_root() == root
    assert paths.install_root() == root
    assert paths.DATA_DIR == root / "data"
    assert paths.CONFIG_DIR == root / "config"
    assert paths.DIST_DIR == root / "dist" / "web"
    assert paths.LEGACY_WEB_DIR == root / "legacy" / "web"
    assert paths.WEB_DIR == root / "dist" / "web"
    assert paths.THEMES_DIR == root / "resources" / "themes"


def test_frozen_layout_splits_bundle_and_install(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    install = tmp_path / "install"
    bundle.mkdir()
    install.mkdir()
    (bundle / "config").mkdir()
    (bundle / "dist" / "web").mkdir(parents=True)
    (bundle / "legacy" / "web").mkdir(parents=True)
    (bundle / "resources" / "themes").mkdir(parents=True)
    exe = install / "my-agent.exe"
    exe.write_bytes(b"")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe), raising=False)

    paths = _reload_paths()
    assert paths.is_frozen() is True
    assert paths.bundle_root() == bundle
    assert paths.install_root() == install
    assert paths.DATA_DIR == install / "data"
    assert paths.CONFIG_DIR == bundle / "config"
    assert paths.DIST_DIR == bundle / "dist" / "web"
    assert paths.LEGACY_WEB_DIR == bundle / "legacy" / "web"
    assert paths.WEB_DIR == bundle / "dist" / "web"
    assert paths.THEMES_DIR == bundle / "resources" / "themes"


def test_frozen_prefers_external_resources_beside_exe(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    install = tmp_path / "install"
    bundle.mkdir()
    install.mkdir()
    (bundle / "config").mkdir()
    (bundle / "dist" / "web").mkdir(parents=True)
    (install / "config").mkdir()
    (install / "dist" / "web").mkdir(parents=True)
    (install / "legacy" / "web").mkdir(parents=True)
    (install / "resources" / "themes").mkdir(parents=True)
    exe = install / "my-agent.exe"
    exe.write_bytes(b"")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe), raising=False)

    paths = _reload_paths()
    assert paths.CONFIG_DIR == install / "config"
    assert paths.DIST_DIR == install / "dist" / "web"
    assert paths.LEGACY_WEB_DIR == install / "legacy" / "web"
    assert paths.WEB_DIR == install / "dist" / "web"
    assert paths.THEMES_DIR == install / "resources" / "themes"
