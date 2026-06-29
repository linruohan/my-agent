"""全局 UI 字体偏好。"""

from __future__ import annotations

from src.ui.prefs.base import UserSettingsBacked
from src.ui.prefs.system_fonts import (
    DEFAULT_FONT_ID,
    SYSTEM_DEFAULT_LABEL,
    css_font_family,
    list_system_fonts,
    normalize_font_id,
)

__all__ = ["DEFAULT_FONT_ID", "FontPrefs"]


class FontPrefs(UserSettingsBacked):
    """字体选择：从系统已安装字体中选取，写入 CSS 变量。"""

    def list_catalog(self) -> list[dict[str, str]]:
        catalog: list[dict[str, str]] = [
            {"id": DEFAULT_FONT_ID, "name": SYSTEM_DEFAULT_LABEL},
        ]
        for name in list_system_fonts():
            catalog.append({"id": name, "name": name})
        return catalog

    def get_font_id(self) -> str:
        settings = self._read_settings()
        return normalize_font_id(settings.get("ui_font"))

    def persist(self, font_id: str) -> None:
        value = normalize_font_id(font_id)
        if value != DEFAULT_FONT_ID and value not in set(list_system_fonts()):
            value = DEFAULT_FONT_ID
        settings = self._read_settings()
        settings["ui_font"] = value
        self._write_settings(settings)

    def build_variables(self, font_id: str | None = None) -> dict[str, str]:
        fid = normalize_font_id(font_id or self.get_font_id())
        family, mono = css_font_family(fid)
        return {
            "--font-family": family,
            "--font-family-mono": mono,
            "--ui-font-id": fid,
        }
