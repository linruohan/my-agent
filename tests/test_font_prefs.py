from __future__ import annotations

from src.infra.user_settings import load_user_settings
from src.ui.font_prefs import (
    build_font_variables,
    get_font_prefs,
    list_font_catalog,
    persist_font_prefs,
)


def test_list_font_catalog():
    catalog = list_font_catalog()
    ids = {item["id"] for item in catalog}
    assert "lxgw-wenkai-gb" in ids
    assert "system" in ids


def test_build_font_variables_lxgw(monkeypatch):
    monkeypatch.setattr(
        "src.ui.prefs.font.FontPrefs.lxgw_font_installed",
        staticmethod(lambda: True),
    )
    vars_ = build_font_variables("lxgw-wenkai-gb")
    assert "LXGW WenKai GB" in vars_["--font-family"]


def test_persist_font_prefs(tmp_path, monkeypatch):
    settings_file = tmp_path / "user_settings.yaml"
    monkeypatch.setattr("src.infra.user_settings.USER_SETTINGS_PATH", settings_file)
    persist_font_prefs("lxgw-wenkai-gb")
    saved = load_user_settings()
    assert saved.get("ui_font") == "lxgw-wenkai-gb"


def test_get_font_prefs_invalid(monkeypatch):
    monkeypatch.setattr(
        "src.infra.user_settings.load_user_settings",
        lambda: {"ui_font": "unknown"},
    )
    assert get_font_prefs() == "system"
