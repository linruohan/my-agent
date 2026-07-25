"""记忆子系统统一门面：写入 / 索引 / 注入相关入口。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from src.memory.context_files import build_memory_prompt_block
from src.memory.memory_index import load_all_memory_entries, read_memory_index, write_memory_index
from src.memory.memory_reader import (
    FindRelevantMemoriesInput,
    FoundMemory,
    build_memory_injection_block,
    find_relevant_memories,
)
from src.memory.memory_writer import (
    ExtractMemoriesInput,
    ExtractMemoriesOutput,
    extract_memories,
    write_structured_memory_note,
)
from src.memory.settings_store import build_critical_rules_prompt_block, is_team_memory_enabled


class MemoryService:
    """对外统一 API，减少双轨写入与分散调用。"""

    def build_prompt_blocks(self) -> dict[str, str]:
        return {
            "critical": build_critical_rules_prompt_block(),
            "memory": build_memory_prompt_block(),
            "index": read_memory_index() or "",
        }

    def list_entries(self, project_root: Path | None = None):
        return load_all_memory_entries(project_root)

    def find_relevant(
        self,
        llm: BaseChatModel,
        *,
        query: str,
        already_surfaced: list[str] | None = None,
        recent_tools: list[str] | None = None,
        max_results: int = 5,
        project_root: Path | None = None,
    ) -> list[FoundMemory]:
        entries = self.list_entries(project_root)
        return find_relevant_memories(
            llm,
            FindRelevantMemoriesInput(
                query=query,
                memory_files=entries,
                already_surfaced=list(already_surfaced or []),
                recent_tools=list(recent_tools or []),
                max_results=max_results,
            ),
        )

    def inject(self, found: list[FoundMemory], project_root: Path | None = None) -> str:
        return build_memory_injection_block(found, project_root)

    def write_note(self, note: str, **kwargs: Any):
        return write_structured_memory_note(note, **kwargs)

    def extract_from_turn(
        self,
        llm: BaseChatModel,
        input_data: ExtractMemoriesInput,
        *,
        project_root: Path | None = None,
    ) -> ExtractMemoriesOutput:
        return extract_memories(llm, input_data, project_root=project_root)

    def rebuild_index(self, project_root: Path | None = None) -> str:
        write_memory_index(project_root)
        return read_memory_index(project_root) or ""

    def team_enabled(self, project_root: Path | None = None) -> bool:
        return is_team_memory_enabled(project_root)


def get_memory_service() -> MemoryService:
    return MemoryService()
