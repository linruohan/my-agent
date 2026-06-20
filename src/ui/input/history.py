"""输入框历史记录持久化。"""

from __future__ import annotations

import json
from pathlib import Path

from src.infra.paths import DATA_DIR

_HISTORY_PATH = DATA_DIR / "input_history.json"
_MAX_ITEMS = 200


def _load() -> list[str]:
    if not _HISTORY_PATH.is_file():
        return []
    try:
        data = json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x) for x in data if str(x).strip()]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save(items: list[str]) -> None:
    _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _HISTORY_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=0), encoding="utf-8")


def list_history() -> list[str]:
    return _load()


def append_history(text: str) -> None:
    body = (text or "").strip()
    if not body:
        return
    items = _load()
    if items and items[0] == body:
        return
    items = [body] + [x for x in items if x != body]
    _save(items[:_MAX_ITEMS])
