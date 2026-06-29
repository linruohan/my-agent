from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.infra.paths import CONFIG_DIR, INSTALL_ROOT


def load_files_config() -> dict[str, Any]:
    path = CONFIG_DIR / "files.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_search_roots() -> list[Path]:
    from src.ui.ui_prefs import get_work_dir

    cfg = load_files_config().get("filesystem", {})
    roots: list[Path] = []
    seen: set[str] = set()

    def add_root(p: Path) -> None:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            roots.append(p.resolve())

    work = get_work_dir()
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


def get_fs_option(key: str, default: Any) -> Any:
    return load_files_config().get("filesystem", {}).get(key, default)
