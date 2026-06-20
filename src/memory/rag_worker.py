"""知识库导入在独立子进程中执行。"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from src.infra.process_executor import run_in_process


def _ingest_files_worker(path_strs: list[str], provider_name: str | None) -> tuple[int, int]:
    from src.infra.config import load_merged_providers
    from src.memory.rag import ingest_files, set_rag_provider

    current, providers = load_merged_providers()
    name = provider_name or current
    provider = providers.get(name)
    if provider is None:
        raise ValueError(f"未知 LLM 提供商: {name}")
    set_rag_provider(provider)
    paths = [Path(p) for p in path_strs]
    return ingest_files(paths, provider)


def ingest_files_in_process(
    paths: list[str | Path],
    provider_name: str | None = None,
    *,
    timeout: float = 3600,
) -> tuple[int, int]:
    path_strs = [str(Path(p).resolve()) for p in paths]
    try:
        return run_in_process(
            _ingest_files_worker,
            path_strs,
            provider_name,
            pool="rag",
            timeout=timeout,
        )
    except Exception as exc:
        logger.exception("[rag-worker] 导入失败")
        raise RuntimeError(str(exc)) from exc
