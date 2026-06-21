"""轻量耗时日志，便于观测 LLM / 工具 / 搜索路径。"""

from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Any, Iterator

from loguru import logger

from src.infra.metrics import metrics_enabled, record_timing


@contextmanager
def log_timing(label: str, **fields: Any) -> Iterator[None]:
    """记录操作耗时（毫秒）及可选结构化字段；AGENT_METRICS=1 时写入 metrics.db。"""
    start = perf_counter()
    try:
        yield
    finally:
        elapsed_ms = max(0, int((perf_counter() - start) * 1000))
        extra = " ".join(f"{k}={v}" for k, v in fields.items() if v is not None)
        if extra:
            logger.info("[timing] {} {}ms {}", label, elapsed_ms, extra)
        else:
            logger.info("[timing] {} {}ms", label, elapsed_ms)
        if metrics_enabled():
            record_timing(label, elapsed_ms, fields)
