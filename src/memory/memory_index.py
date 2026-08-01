"""记忆索引管理：支持全局+项目合并，索引常驻+内容按需加载。"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from src.infra.paths import global_config_dir, project_config_dir

_MAX_INDEX_LINES = 200
_MAX_INDEX_BYTES = 25000
_MAX_INDEX_CHARS = 2500
_INDEX_DEBOUNCE_SEC = 1.5

_debounce_lock = threading.Lock()
_pending_roots: set[str] = set()
_debounce_timer: threading.Timer | None = None


@dataclass
class MemoryEntry:
    file_name: str
    name: str
    description: str
    memory_type: str
    created: str
    updated: str
    tags: list[str]
    path: Path


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---\n")
    if end == -1:
        return {}, text
    try:
        frontmatter = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        frontmatter = {}
    body = text[end + 5 :].strip()
    return frontmatter, body


def _load_memory_entry(path: Path) -> MemoryEntry | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return None
    if not text:
        return None
    frontmatter, _ = _parse_frontmatter(text)
    return MemoryEntry(
        file_name=path.name,
        name=frontmatter.get("name", path.stem),
        description=frontmatter.get("description", ""),
        memory_type=frontmatter.get("type", "user"),
        created=frontmatter.get("created", ""),
        updated=frontmatter.get("updated", ""),
        tags=frontmatter.get("tags", []),
        path=path,
    )


def load_all_memory_entries(project_root: Path | None = None) -> list[MemoryEntry]:
    """加载所有记忆文件的条目（只读 frontmatter）。"""
    entries: list[MemoryEntry] = []
    visited = set()

    def _load_from_dir(memory_dir: Path) -> None:
        if not memory_dir.is_dir():
            return
        for path in sorted(memory_dir.glob("*.md")):
            if path in visited:
                continue
            visited.add(path)
            entry = _load_memory_entry(path)
            if entry:
                entries.append(entry)

    _load_from_dir(global_config_dir() / "memory")
    _load_from_dir(project_config_dir(project_root) / "memory")

    from src.memory.settings_store import is_team_memory_enabled

    if is_team_memory_enabled(project_root):
        _load_from_dir(project_config_dir(project_root) / "memory" / "team")

    return entries


def build_memory_index(project_root: Path | None = None) -> str:
    """构建 MEMORY.md 索引内容。"""
    entries = load_all_memory_entries(project_root)
    if not entries:
        return "# Agent 记忆索引\n\n## 记忆清单\n暂无记忆\n"

    parts = ["# Agent 记忆索引\n\n## 记忆清单"]
    for entry in entries:
        parts.append(f"- **{entry.file_name}**（{entry.memory_type}）：{entry.description}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts.append(f"\n## 统计信息")
    parts.append(f"- 最后更新：{now}")
    parts.append(f"- 记忆数量：{len(entries)}")
    parts.append("\n## 重要提醒")
    parts.append("- 行为规则（\"必须\"、\"禁止\"）已提权到 .my-agent/rules/")
    parts.append("- 记忆不是真理，使用前请主动验证")

    index_text = "\n".join(parts)
    lines = index_text.count("\n") + 1
    bytes_len = len(index_text.encode("utf-8"))

    if lines > _MAX_INDEX_LINES or bytes_len > _MAX_INDEX_BYTES or len(index_text) > _MAX_INDEX_CHARS:
        truncated = index_text[:_MAX_INDEX_CHARS - 30].rstrip()
        return truncated + "\n\n[记忆索引已截断，部分内容未加载]"

    return index_text


def write_memory_index(project_root: Path | None = None) -> None:
    """写入 MEMORY.md 索引文件。"""
    index_text = build_memory_index(project_root)
    project_dir = project_config_dir(project_root)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "MEMORY.md").write_text(index_text + "\n", encoding="utf-8")


def _root_key(project_root: Path | None) -> str:
    if project_root is None:
        return ""
    return str(Path(project_root).resolve())


def _flush_scheduled_memory_indexes() -> None:
    global _debounce_timer
    with _debounce_lock:
        roots = list(_pending_roots)
        _pending_roots.clear()
        _debounce_timer = None
    for key in roots:
        try:
            write_memory_index(None if key == "" else Path(key))
        except Exception:
            logger.exception("防抖写入 MEMORY.md 失败 root={}", key or "(default)")


def schedule_write_memory_index(
    project_root: Path | None = None,
    *,
    delay: float = _INDEX_DEBOUNCE_SEC,
) -> None:
    """合并短时间内的多次索引重建，避免连续写盘。"""
    global _debounce_timer
    key = _root_key(project_root)
    with _debounce_lock:
        _pending_roots.add(key)
        if _debounce_timer is not None:
            _debounce_timer.cancel()
            _debounce_timer = None
        if delay <= 0:
            roots = list(_pending_roots)
            _pending_roots.clear()
        else:
            _debounce_timer = threading.Timer(delay, _flush_scheduled_memory_indexes)
            _debounce_timer.daemon = True
            _debounce_timer.start()
            return
    for root_key in roots:
        write_memory_index(None if root_key == "" else Path(root_key))


def flush_memory_index_writes() -> None:
    """立即刷出待写入的记忆索引（测试/关停用）。"""
    global _debounce_timer
    with _debounce_lock:
        if _debounce_timer is not None:
            _debounce_timer.cancel()
            _debounce_timer = None
        roots = list(_pending_roots)
        _pending_roots.clear()
    for key in roots:
        write_memory_index(None if key == "" else Path(key))


def read_memory_index(project_root: Path | None = None) -> str:
    """读取 MEMORY.md 索引文件。"""
    paths = [
        global_config_dir() / "MEMORY.md",
        project_config_dir(project_root) / "MEMORY.md",
    ]
    parts = []
    for path in paths:
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8", errors="ignore").strip())
    if not parts:
        return ""
    return "\n\n---\n\n".join(parts)