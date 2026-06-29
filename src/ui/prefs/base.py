"""用户偏好基类：统一读写 user_settings.yaml。"""

from __future__ import annotations

from typing import Any, Callable


class UserSettingsBacked:
    """基于 user_settings.yaml 的偏好存储基类。"""

    def __init__(
        self,
        *,
        load_fn: Callable[[], dict[str, Any]] | None = None,
        save_fn: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._load_override = load_fn
        self._save_override = save_fn

    def _ui_section(self, *, create: bool = False) -> dict[str, Any]:
        settings = self._read_settings()
        if create:
            return settings.setdefault("ui", {})
        return settings.get("ui", {}) or {}

    def _read_settings(self) -> dict[str, Any]:
        if self._load_override is not None:
            return self._load_override()
        from src.infra import user_settings as us

        return us.load_user_settings()

    def _write_settings(self, settings: dict[str, Any]) -> None:
        if self._save_override is not None:
            self._save_override(settings)
        else:
            from src.infra import user_settings as us

            us.save_user_settings(settings)
