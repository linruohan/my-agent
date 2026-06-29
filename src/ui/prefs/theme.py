"""主题 ID 与外观偏好。"""

from __future__ import annotations

from src.infra.paths import THEMES_DIR
from src.ui.prefs.base import UserSettingsBacked

DEFAULT_THEME_ID = "macos"
DEFAULT_APPEARANCE = "dark"
VALID_APPEARANCES = frozenset({"light", "dark", "system"})


class ThemePrefs(UserSettingsBacked):
    """主题选择与外观模式偏好。"""

    @staticmethod
    def _resolve_theme_id(theme_id: str) -> str:
        if (THEMES_DIR / f"{theme_id}.json").exists():
            return theme_id
        if (THEMES_DIR / "macos.json").exists():
            return "macos"
        return "default"

    @staticmethod
    def _normalize_appearance(appearance: str) -> str:
        if appearance in VALID_APPEARANCES:
            return appearance
        return DEFAULT_APPEARANCE

    def get_prefs(self) -> tuple[str, str]:
        settings = self._read_settings()
        theme_id = settings.get("ui_theme") or DEFAULT_THEME_ID
        appearance = settings.get("appearance") or DEFAULT_APPEARANCE
        return self._resolve_theme_id(theme_id), self._normalize_appearance(appearance)

    def persist(self, theme_id: str, appearance: str) -> None:
        theme_id = self._resolve_theme_id(theme_id)
        appearance = self._normalize_appearance(appearance)
        settings = self._read_settings()
        settings["ui_theme"] = theme_id
        settings["appearance"] = appearance
        self._write_settings(settings)
