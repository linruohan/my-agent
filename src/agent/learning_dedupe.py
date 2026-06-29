"""学习闭环去重：轮次指纹、MEMORY / Skill 内容查重。"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.database import app_db_path
from src.database.schemas.learning_records import SCHEMA
from src.infra.sqlite_store import ReusableSqliteStore
from src.memory.context_files import memory_file_path, read_context_file
from src.ui.skill.catalog import resolve_skill


def normalize_text(text: str) -> str:
    """折叠空白并小写，便于内容查重。"""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def normalize_memory_line(note: str) -> str:
    line = (note or "").strip()
    line = re.sub(r"^[-*•]\s*", "", line)
    return normalize_text(line)


def _normalize_arg_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, list):
        return [_normalize_arg_value(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _normalize_arg_value(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    return normalize_text(str(value))


def _normalize_tool_args(args: Any) -> str:
    if args is None:
        return ""
    if isinstance(args, dict):
        normalized = {str(k): _normalize_arg_value(v) for k, v in sorted(args.items(), key=lambda kv: str(kv[0]))}
        return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return normalize_text(str(args))


def _tool_call_signature(tool_call: dict[str, Any]) -> str:
    name = str(tool_call.get("name") or "")
    args = tool_call.get("args")
    if args is None and isinstance(tool_call, dict):
        args = {k: v for k, v in tool_call.items() if k not in ("name", "id", "type")}
    return f"{name}({_normalize_tool_args(args)})"


def turn_fingerprint(user_message: str, tool_calls: list[dict[str, Any]]) -> str:
    """同一用户意图 + 工具序列（含参数）视为同一轮次。"""
    user = normalize_text(user_message)
    tools = "|".join(_tool_call_signature(tc) for tc in tool_calls)
    payload = f"{user}\n{tools}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:32]


class LearningLedger(ReusableSqliteStore):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(db_path or app_db_path())
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def has_fingerprint(self, fingerprint: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM learning_records WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        return row is not None

    def record(
        self,
        fingerprint: str,
        *,
        skill_name: str = "",
        memory_note: str = "",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO learning_records (fingerprint, skill_name, memory_note, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(fingerprint) DO UPDATE SET
                    skill_name = excluded.skill_name,
                    memory_note = excluded.memory_note,
                    created_at = excluded.created_at
                """,
                (fingerprint, skill_name.strip(), memory_note.strip(), self._now()),
            )


_ledger: LearningLedger | None = None


def shared_ledger() -> LearningLedger:
    global _ledger
    if _ledger is None:
        _ledger = LearningLedger()
    return _ledger


def memory_note_exists(note: str) -> bool:
    """MEMORY.md 中是否已有相同或极相似条目。"""
    target = normalize_memory_line(note)
    if not target or len(target) < 4:
        return False
    memory_text = read_context_file(memory_file_path(), max_chars=50000)
    if not memory_text:
        return False
    blob = normalize_text(memory_text)
    if target in blob:
        return True
    for line in memory_text.splitlines():
        line_norm = normalize_memory_line(line)
        if not line_norm:
            continue
        if line_norm == target:
            return True
        if len(target) >= 12 and (target in line_norm or line_norm in target):
            return True
    return False


def skill_instructions_exist(name: str, instructions: str) -> bool:
    """Skill 正文中是否已包含相同步骤说明。"""
    block = normalize_text(instructions)
    if not block or len(block) < 3:
        return False
    resolved = resolve_skill(name)
    if not resolved:
        return False
    _, skill_md = resolved
    try:
        existing = skill_md.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return block in normalize_text(existing)
