"""聊天布局偏好：宽度、工作目录。"""

from __future__ import annotations

from pathlib import Path

from src.ui.prefs.base import UserSettingsBacked

DEFAULT_CHAT_WIDTH_PCT = 85
MIN_CHAT_WIDTH_PCT = 50
MAX_CHAT_WIDTH_PCT = 100


class LayoutPrefs(UserSettingsBacked):
    """聊天区宽度与工作目录偏好。"""

    @staticmethod
    def clamp_width_pct(value: int | float) -> int:
        try:
            n = int(round(float(value)))
        except (TypeError, ValueError):
            n = DEFAULT_CHAT_WIDTH_PCT
        return max(MIN_CHAT_WIDTH_PCT, min(MAX_CHAT_WIDTH_PCT, n))

    def get_chat_width_pct(self) -> int:
        ui = self._ui_section()
        return self.clamp_width_pct(ui.get("chat_width_pct", DEFAULT_CHAT_WIDTH_PCT))

    def persist_chat_width_pct(self, pct: int | float) -> int:
        value = self.clamp_width_pct(pct)
        settings = self._read_settings()
        ui = settings.setdefault("ui", {})
        ui["chat_width_pct"] = value
        self._write_settings(settings)
        return value

    def get_work_dir(self) -> Path | None:
        ui = self._ui_section()
        raw = (ui.get("work_dir") or "").strip()
        if not raw:
            return None
        p = Path(raw).expanduser().resolve()
        return p if p.is_dir() else None

    def persist_work_dir(self, path: str | Path) -> Path:
        p = Path(path).expanduser().resolve()
        if not p.is_dir():
            raise NotADirectoryError(f"不是有效目录: {p}")
        settings = self._read_settings()
        ui = settings.setdefault("ui", {})
        ui["work_dir"] = str(p)
        self._write_settings(settings)
        return p

    @staticmethod
    def format_work_dir_display(path: Path | None) -> str:
        if path is None:
            return "点击选择工作目录"
        return str(path)
