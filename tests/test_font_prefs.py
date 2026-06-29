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
    assert "system" in ids
    assert len(catalog) >= 2


def test_build_font_variables_custom():
    vars_ = build_font_variables("Segoe UI")
    assert "Segoe UI" in vars_["--font-family"]
    assert vars_["--ui-font-id"] == "Segoe UI"


def test_persist_font_prefs(tmp_path, monkeypatch):
    settings_file = tmp_path / "user_settings.yaml"
    monkeypatch.setattr("src.infra.user_settings.USER_SETTINGS_PATH", settings_file)
    monkeypatch.setattr(
        "src.ui.prefs.system_fonts.list_system_fonts",
        lambda **_: ["Segoe UI", "Microsoft YaHei"],
    )
    persist_font_prefs("Segoe UI")
    saved = load_user_settings()
    assert saved.get("ui_font") == "Segoe UI"


def test_get_font_prefs_invalid(monkeypatch):
    monkeypatch.setattr(
        "src.infra.user_settings.load_user_settings",
        lambda: {"ui_font": "unknown-font-xyz"},
    )
    assert get_font_prefs() == "unknown-font-xyz"


def test_legacy_lxgw_migrates_to_system(monkeypatch):
    monkeypatch.setattr(
        "src.infra.user_settings.load_user_settings",
        lambda: {"ui_font": "lxgw-wenkai-gb"},
    )
    assert get_font_prefs() == "system"
