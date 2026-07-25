"""记忆读取器：findRelevantMemories 小模型选择器，选择最相关的记忆。"""

from __future__ import annotations

import hashlib
import json
import re
import time
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
_CACHE_TTL_SEC = 120.0
_cache: dict[str, tuple[float, list[FoundMemory]]] = {}


def clear_memory_selection_cache() -> None:
    _cache.clear()


def _selection_cache_key(input_data: FindRelevantMemoriesInput) -> str:
    files = sorted(e.file_name for e in input_data.memory_files)
    surfaced = sorted(input_data.already_surfaced)
    tools = sorted(input_data.recent_tools)
    raw = json.dumps(
        {
            "q": (input_data.query or "").strip().lower(),
            "files": files,
            "surfaced": surfaced,
            "tools": tools,
            "n": input_data.max_results,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


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
    _MAX_SURFACED = 100

    def add_surfaced(self, file_names: list[str]) -> None:
        self.already_surfaced_memories.update(file_names)
        if len(self.already_surfaced_memories) > self._MAX_SURFACED:
            self.already_surfaced_memories = set(list(self.already_surfaced_memories)[-self._MAX_SURFACED:])

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


def _should_filter_by_tool(entry: MemoryEntry, recent_tools: list[str]) -> bool:
    """判断记忆是否应根据最近使用的工具进行过滤。
    
    排除最近用过的工具的「用法参考文档」，但保留「警告、坑点、已知问题」。
    """
    if not recent_tools:
        return False

    description_lower = entry.description.lower()
    name_lower = entry.name.lower()

    warning_keywords = ["警告", "坑", "注意", "问题", "错误", "失败", "bug", "warning", "caution", "issue", "error", "fail"]

    for tool_name in recent_tools:
        tool_lower = tool_name.lower()
        if tool_lower in description_lower or tool_lower in name_lower:
            for keyword in warning_keywords:
                if keyword.lower() in description_lower or keyword.lower() in name_lower:
                    return False
            return True
    return False


def find_relevant_memories(
    llm: BaseChatModel,
    input_data: FindRelevantMemoriesInput,
) -> list[FoundMemory]:
    """使用小模型选择最相关的记忆（短时缓存，降低重复查询成本）。"""
    entries = input_data.memory_files

    entries = [e for e in entries if e.file_name not in input_data.already_surfaced]

    entries = [e for e in entries if not _should_filter_by_tool(e, input_data.recent_tools)]

    if not entries:
        return []

    cache_key = _selection_cache_key(input_data)
    cached = _cache.get(cache_key)
    if cached and (time.time() - cached[0]) < _CACHE_TTL_SEC:
        return list(cached[1])

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
        _cache[cache_key] = (time.time(), list(found))
        if len(_cache) > 64:
            # 简单淘汰最旧条目
            oldest = min(_cache.items(), key=lambda kv: kv[1][0])[0]
            _cache.pop(oldest, None)
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

        from src.memory.memory_validator import build_verification_prompt

        verify = build_verification_prompt(content)
        verify_block = f"{verify}\n\n" if verify else ""

        injection = f"<system-reminder>\n{stale_warning}{verify_block}{content}\n</system-reminder>"
        parts.append(injection)

    return "\n\n".join(parts)