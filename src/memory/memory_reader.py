"""记忆读取器：findRelevantMemories 小模型选择器，选择最相关的记忆。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from src.memory.memory_index import MemoryEntry, load_all_memory_entries

_MAX_RESULTS = 5
_STALE_DAYS = 2


@dataclass
class FoundMemory:
    file_name: str
    confidence: float
    reason: str


@dataclass
class FindRelevantMemoriesInput:
    query: str
    memory_files: list[MemoryEntry]
    already_surfaced: list[str]
    recent_tools: list[str]
    max_results: int = _MAX_RESULTS


@dataclass
class ConversationState:
    already_surfaced_memories: set[str] = field(default_factory=set)

    def add_surfaced(self, file_names: list[str]) -> None:
        self.already_surfaced_memories.update(file_names)

    def clear(self) -> None:
        self.already_surfaced_memories.clear()


def _parse_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {}


def _is_stale(entry: MemoryEntry) -> bool:
    """判断记忆是否过期（2天前的记忆标记为过期）。"""
    if not entry.updated:
        return False
    try:
        updated_date = datetime.strptime(entry.updated, "%Y-%m-%d")
        delta = datetime.now() - updated_date
        return delta.days >= _STALE_DAYS
    except ValueError:
        return False


def _build_memory_list(entries: list[MemoryEntry]) -> str:
    """构建记忆清单文本，用于发送给选择器模型。"""
    lines = []
    for entry in entries:
        stale_marker = " [STALE]" if _is_stale(entry) else ""
        lines.append(f"- {entry.file_name}: {entry.description}{stale_marker}")
    return "\n".join(lines)


def find_relevant_memories(
    llm: BaseChatModel,
    input_data: FindRelevantMemoriesInput,
) -> list[FoundMemory]:
    """使用小模型选择最相关的记忆。"""
    entries = input_data.memory_files

    entries = [e for e in entries if e.file_name not in input_data.already_surfaced]

    if not entries:
        return []

    memory_list = _build_memory_list(entries)
    max_results = min(input_data.max_results, _MAX_RESULTS)

    prompt = f"""Query: {input_data.query}

Available memories:
{memory_list}

Return top-{max_results} memories that you are CERTAIN will be helpful.
Only include memories that directly relate to the query.
Be selective and discerning.
If uncertain, do not include.

Format: JSON object with "memories" array containing file_name, confidence (0-1), and reason.
"""

    try:
        msg = llm.invoke(
            [
                SystemMessage(content="你是记忆选择器，只输出 JSON。"),
                HumanMessage(content=prompt),
            ]
        )
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        result = _parse_json(content)
        memories = result.get("memories", [])

        found = []
        for mem in memories[:max_results]:
            found.append(FoundMemory(
                file_name=str(mem.get("file_name", "")),
                confidence=float(mem.get("confidence", 0)),
                reason=str(mem.get("reason", "")),
            ))
        return found
    except Exception:
        logger.exception("记忆选择 LLM 调用失败")
        return []


def read_memory_content(file_name: str, project_root: Path | None = None) -> str | None:
    """读取记忆文件的完整内容。"""
    from src.infra.paths import global_config_dir, project_config_dir

    search_paths = [
        global_config_dir() / "memory" / file_name,
        project_config_dir(project_root) / "memory" / file_name,
        project_config_dir(project_root) / "memory" / "team" / file_name,
    ]

    for path in search_paths:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="ignore").strip()

    return None


def build_memory_injection_block(
    found_memories: list[FoundMemory],
    project_root: Path | None = None,
) -> str:
    """构建注入上下文的记忆块，包含老化警告。"""
    if not found_memories:
        return ""

    parts = []
    for found in found_memories:
        content = read_memory_content(found.file_name, project_root)
        if not content:
            continue

        entry = next(
            (e for e in load_all_memory_entries(project_root) if e.file_name == found.file_name),
            None
        )

        stale_warning = ""
        if entry and _is_stale(entry):
            try:
                updated_date = datetime.strptime(entry.updated, "%Y-%m-%d")
                days = (datetime.now() - updated_date).days
                stale_warning = f"This memory was saved {days} days ago. Verify it's still accurate before acting on it.\n\n"
            except ValueError:
                pass

        injection = f"<system-reminder>\n{stale_warning}{content}\n</system-reminder>"
        parts.append(injection)

    return "\n\n".join(parts)