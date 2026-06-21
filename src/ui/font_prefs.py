"""全局 UI 字体偏好。"""

from __future__ import annotations

from src.infra.user_settings import load_user_settings, save_user_settings

DEFAULT_FONT_ID = "system"

FONT_CATALOG: dict[str, dict[str, str]] = {
    "system": {
        "name": "系统默认",
        "family": '"Segoe UI", system-ui, -apple-system, sans-serif',
        "mono": 'Consolas, "Courier New", monospace',
    },
    "lxgw-wenkai-gb": {
        "name": "LXGW WenKai GB",
        "family": '"LXGW WenKai GB", "Segoe UI", system-ui, sans-serif',
        "mono": '"LXGW WenKai GB", Consolas, monospace',
    },
}


def list_font_catalog() -> list[dict[str, str]]:
    return [{"id": fid, "name": meta["name"]} for fid, meta in FONT_CATALOG.items()]


def get_font_prefs() -> str:
    settings = load_user_settings()
    font_id = settings.get("ui_font") or DEFAULT_FONT_ID
    if font_id not in FONT_CATALOG:
        font_id = DEFAULT_FONT_ID
    return font_id


def persist_font_prefs(font_id: str) -> None:
    if font_id not in FONT_CATALOG:
        font_id = DEFAULT_FONT_ID
    settings = load_user_settings()
    settings["ui_font"] = font_id
    save_user_settings(settings)


def build_font_variables(font_id: str | None = None) -> dict[str, str]:
    fid = font_id or get_font_prefs()
    if fid not in FONT_CATALOG:
        fid = DEFAULT_FONT_ID
    meta = FONT_CATALOG[fid]
    return {
        "--font-family": meta["family"],
        "--font-family-mono": meta["mono"],
        "--ui-font-id": fid,
    }
