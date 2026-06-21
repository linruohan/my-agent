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
    cfg = load_files_config().get("filesystem", {})
    roots: list[Path] = []
    for raw in cfg.get("search_roots", ["~", "data/workspace"]):
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = (INSTALL_ROOT / p).resolve()
        else:
            p = p.resolve()
        if p.exists():
            roots.append(p)
    if not roots:
        roots.append(Path.home())
    return roots


def get_fs_option(key: str, default: Any) -> Any:
    return load_files_config().get("filesystem", {}).get(key, default)
