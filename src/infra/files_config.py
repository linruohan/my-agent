from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import yaml

from src.infra.paths import CONFIG_DIR, INSTALL_ROOT


class FilesConfig:
    """files.yaml 文件系统配置。"""

    def __init__(
        self,
        config_path: Path | None = None,
        *,
        work_dir_getter: Callable[[], Path | None] | None = None,
    ) -> None:
        self._config_path = config_path or (CONFIG_DIR / "files.yaml")
        self._work_dir_getter = work_dir_getter

    def load(self) -> dict[str, Any]:
        if not self._config_path.exists():
            return {}
        with self._config_path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def get_fs_option(self, key: str, default: Any) -> Any:
        return self.load().get("filesystem", {}).get(key, default)

    def get_search_roots(self) -> list[Path]:
        cfg = self.load().get("filesystem", {})
        roots: list[Path] = []
        seen: set[str] = set()

        def add_root(p: Path) -> None:
            key = str(p.resolve())
            if key not in seen:
                seen.add(key)
                roots.append(p.resolve())

        if self._work_dir_getter:
            work = self._work_dir_getter()
            if work:
                add_root(work)

        for raw in cfg.get("search_roots", ["~", "data/workspace"]):
            p = Path(raw).expanduser()
            if not p.is_absolute():
                p = (INSTALL_ROOT / p).resolve()
            else:
                p = p.resolve()
            if p.exists():
                add_root(p)
        if not roots:
            roots.append(Path.home())
        return roots


def _default_work_dir_getter() -> Path | None:
    from src.ui.prefs import layout_prefs

    return layout_prefs.get_work_dir()


files_config = FilesConfig(work_dir_getter=_default_work_dir_getter)

load_files_config = files_config.load
get_search_roots = files_config.get_search_roots
get_fs_option = files_config.get_fs_option

__all__ = [
    "FilesConfig",
    "files_config",
    "get_fs_option",
    "get_search_roots",
    "load_files_config",
]
