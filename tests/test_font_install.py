"""字体安装检测测试。"""

from __future__ import annotations

from src.ui import font_prefs as fp


def test_lxgw_font_installed_detects_woff2(tmp_path, monkeypatch):
    font_dir = tmp_path / "web" / "fonts" / "lxgwwenkaigb-regular"
    font_dir.mkdir(parents=True)
    (font_dir / "0.woff2").write_bytes(b"x")
    monkeypatch.setattr("src.infra.paths.WEB_DIR", tmp_path / "web")
    assert fp.lxgw_font_installed() is True


def test_build_font_variables_fallback_without_lxgw(monkeypatch):
    monkeypatch.setattr(fp, "lxgw_font_installed", lambda: False)
    vars_ = fp.build_font_variables("lxgw-wenkai-gb")
    assert vars_["--ui-font-id"] == "system"
