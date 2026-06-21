"""从 themes/*.json 加载 gpui 主题并映射为 Web CSS 变量。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from src.infra.paths import THEMES_DIR
from src.infra.user_settings import load_user_settings, save_user_settings

# 语义变量 -> gpui 键回退链（按优先级）
_SEMANTIC: dict[str, tuple[str, ...]] = {
    "--bg-app": ("background",),
    "--fg": ("foreground",),
    "--border": ("border",),
    "--ring": ("ring", "primary.background"),
    "--bg-muted": ("muted.background", "secondary.background", "panel.background"),
    "--fg-muted": ("muted.foreground",),
    "--bg-sidebar": (
        "sidebar.background",
        "tab_bar.background",
        "title_bar.background",
        "panel.background",
        "muted.background",
        "background",
    ),
    "--fg-sidebar": ("sidebar.foreground", "tab.foreground", "foreground"),
    "--border-sidebar": ("sidebar.border", "title_bar.border", "border"),
    "--bg-sidebar-accent": ("sidebar.accent.background", "list.hover.background", "accent.background"),
    "--fg-sidebar-accent": ("sidebar.accent.foreground", "accent.foreground", "foreground"),
    "--primary-bg": ("primary.background",),
    "--primary-fg": ("primary.foreground",),
    "--primary-hover": ("primary.hover.background", "primary.active.background", "primary.background"),
    "--secondary-bg": ("secondary.background", "muted.background", "panel.background"),
    "--secondary-fg": ("secondary.foreground", "foreground"),
    "--accent-bg": ("accent.background", "secondary.background"),
    "--accent-fg": ("accent.foreground", "foreground"),
    "--bg-popover": ("popover.background", "list.background", "background"),
    "--fg-popover": ("popover.foreground", "foreground"),
    "--bg-panel": ("panel.background", "list.even.background", "muted.background"),
    "--bg-list": ("list.background", "background"),
    "--bg-list-hover": ("list.hover.background", "list.active.background", "muted.background"),
    "--bg-input": ("input.background", "popover.background", "list.background", "background"),
    "--input-border": ("input.border", "border"),
    "--link": ("link.foreground", "link.active.foreground", "primary.background"),
    "--link-hover": ("link.hover.foreground", "link.foreground"),
    "--danger": ("danger.background", "highlight.error", "base.red"),
    "--danger-fg": ("danger.foreground", "foreground"),
    "--success": ("success.background", "highlight.success", "base.green"),
    "--success-fg": ("success.foreground", "foreground"),
    "--info": ("info.background", "highlight.info", "base.blue"),
    "--info-fg": ("info.foreground", "foreground"),
    "--warning": ("warning.background", "highlight.warning", "base.yellow"),
    "--scrollbar-thumb": ("scrollbar.thumb.background", "scrollbar.thumb.hover.background", "muted.foreground"),
    "--scrollbar-track": ("scrollbar.background", "background"),
    "--bg-titlebar": ("title_bar.background", "tab_bar.background", "panel.background"),
    "--bg-tabbar": ("tab_bar.background", "panel.background"),
    "--selection": ("selection.background", "primary.background", "ring"),
    "--bg-chat": ("list.even.background", "muted.background", "panel.background", "background"),
    "--user-bubble-bg": ("primary.background",),
    "--user-bubble-fg": ("primary.foreground",),
    "--assistant-bubble-bg": ("popover.background", "panel.background", "list.background", "muted.background"),
    "--assistant-bubble-fg": ("popover.foreground", "foreground"),
    "--assistant-bubble-border": ("border",),
    "--meta-bg": ("muted.background", "secondary.background", "accent.background"),
    "--meta-fg": ("muted.foreground",),
    "--code-bg": ("highlight.editor.background", "muted.background", "panel.background"),
    "--code-fg": ("highlight.editor.foreground", "foreground"),
    "--avatar-bg": ("accent.background", "muted.background", "secondary.background"),
    "--session-active-bg": ("list.active.background", "sidebar.accent.background", "muted.background"),
    "--session-active-fg": ("list.active.border", "primary.background", "foreground"),
    "--composer-bg": ("panel.background", "muted.background", "secondary.background"),
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def gpui_key_to_css_var(key: str, *, prefix: str = "gp") -> str:
    """primary.background -> --gp-primary-background"""
    return f"--{prefix}-" + key.replace(".", "-")


def list_theme_files() -> list[Path]:
    return sorted(THEMES_DIR.glob("*.json"))


def list_theme_catalog() -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for path in list_theme_files():
        try:
            data = _load_json(path)
        except (json.JSONDecodeError, OSError):
            continue
        modes = sorted({v.get("mode", "light") for v in data.get("themes", [])})
        catalog.append(
            {
                "id": path.stem,
                "name": data.get("name") or path.stem.replace("-", " ").title(),
                "modes": modes,
            }
        )
    return catalog


def get_theme_prefs() -> tuple[str, str]:
    settings = load_user_settings()
    theme_id = settings.get("ui_theme") or "default"
    appearance = settings.get("appearance") or "dark"
    if appearance not in ("light", "dark", "system"):
        appearance = "dark"
    if not (THEMES_DIR / f"{theme_id}.json").exists():
        theme_id = "default"
    return theme_id, appearance


def persist_theme_prefs(theme_id: str, appearance: str) -> None:
    if not (THEMES_DIR / f"{theme_id}.json").exists():
        theme_id = "default"
    if appearance not in ("light", "dark", "system"):
        appearance = "dark"
    settings = load_user_settings()
    settings["ui_theme"] = theme_id
    settings["appearance"] = appearance
    save_user_settings(settings)


def _flatten_highlight(highlight: dict[str, Any], prefix: str = "highlight") -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, val in highlight.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(val, dict):
            if "color" in val:
                flat[full] = val["color"]
            else:
                flat.update(_flatten_highlight(val, full))
        elif isinstance(val, str):
            flat[full] = val
    return flat


def _pick_variant(data: dict[str, Any], appearance: str) -> dict[str, Any]:
    variants = data.get("themes") or []
    if not variants:
        return {}

    for v in variants:
        if v.get("mode") == appearance:
            return v
    for v in variants:
        if v.get("is_default"):
            return v
    return variants[0]


def _resolve_color(colors: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        if key in colors and colors[key]:
            return colors[key]
    return None


def resolve_effective_appearance(appearance: str) -> str:
    if appearance in ("light", "dark"):
        return appearance
    if appearance != "system":
        return "dark"
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\PersonalizeColors",
            ) as key:
                val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return "light" if val else "dark"
        except OSError:
            pass
    return "dark"


def _export_raw_gpui_vars(colors: dict[str, str]) -> dict[str, str]:
    """JSON 中每个颜色键都导出为 --gp-*，供 CSS fallback 或直接引用。"""
    return {gpui_key_to_css_var(k): v for k, v in colors.items() if v}


def build_css_variables(theme_id: str, appearance: str) -> dict[str, str]:
    effective = resolve_effective_appearance(appearance)
    path = THEMES_DIR / f"{theme_id}.json"
    if not path.exists():
        path = THEMES_DIR / "default.json"
    data = _load_json(path)
    variant = _pick_variant(data, effective)
    colors: dict[str, str] = dict(variant.get("colors") or {})
    colors.update(_flatten_highlight(variant.get("highlight") or {}))

    css: dict[str, str] = _export_raw_gpui_vars(colors)

    for css_key, fallbacks in _SEMANTIC.items():
        val = _resolve_color(colors, fallbacks)
        if val:
            css[css_key] = val

    syntax = (variant.get("highlight") or {}).get("syntax") or {}
    for name, spec in syntax.items():
        if isinstance(spec, dict) and "color" in spec:
            css[f"--syntax-{name.replace('.', '-')}"] = spec["color"]
            css[gpui_key_to_css_var(f"syntax.{name}", prefix="gp")] = spec["color"]

    css.setdefault("--radius-input", "6px")
    css.setdefault("--radius-bubble", "12px")
    css.setdefault("--radius-chip", "12px")
    css.setdefault("--radius-avatar", "16px")
    css.setdefault("--font-body", "14px")
    css.setdefault("--font-meta", "12px")
    css.setdefault("--font-caption", "11px")
    css.setdefault("--bubble-inset", "12px")
    css.setdefault("--message-gap", "14px")

    css["--theme-name"] = data.get("name") or theme_id
    css["--theme-mode"] = variant.get("mode") or effective
    css["--theme-id"] = theme_id
    return css


def build_theme_payload(theme_id: str, appearance: str) -> dict[str, Any]:
    return {
        "theme_id": theme_id,
        "appearance": appearance,
        "variables": build_css_variables(theme_id, appearance),
        "catalog": list_theme_catalog(),
    }
