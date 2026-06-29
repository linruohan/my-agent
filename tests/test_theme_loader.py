from __future__ import annotations

from src.ui.theme_loader import (
    build_css_variables,
    get_theme_prefs,
    gpui_key_to_css_var,
    list_theme_catalog,
    persist_theme_prefs,
)


def test_list_theme_catalog_includes_default():
    catalog = list_theme_catalog()
    ids = {t["id"] for t in catalog}
    assert "default" in ids
    assert "macos" in ids
    assert all("name" in t and "modes" in t for t in catalog)


def test_build_macos_theme_variables():
    vars_ = build_css_variables("macos", "light")
    assert vars_["--primary-bg"] == "#007AFF"
    assert vars_["--theme-name"] == "macOS"


def test_build_css_variables_has_semantic_keys():
    vars_ = build_css_variables("default", "dark")
    assert "--bg-app" in vars_
    assert "--user-bubble-bg" in vars_
    assert "--radius-bubble" in vars_


def test_catppuccin_exports_all_gpui_keys():
    vars_ = build_css_variables("catppuccin", "dark")
    assert "--gp-background" in vars_
    assert "--gp-primary-background" in vars_
    assert vars_["--bg-sidebar"] == vars_["--gp-tab_bar-background"]
    assert "--bg-chat" in vars_


def test_gruvbox_resolves_highlight_info():
    vars_ = build_css_variables("gruvbox", "dark")
    assert "--info" in vars_
    assert vars_["--info"]  # non-empty


def test_gpui_key_to_css_var():
    assert gpui_key_to_css_var("primary.background") == "--gp-primary-background"


def test_get_theme_prefs_fallback(monkeypatch):
    monkeypatch.setattr(
        "src.infra.user_settings.load_user_settings",
        lambda: {"ui_theme": "missing-theme", "appearance": "invalid"},
    )
    theme_id, appearance = get_theme_prefs()
    assert theme_id == "macos"
    assert appearance == "dark"
