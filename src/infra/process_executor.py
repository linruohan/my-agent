"""共享 ProcessPoolExecutor（spawn），供 OCR / Agent 工具 / UI 重任务使用。"""

from __future__ import annotations

import atexit
import multiprocessing
import threading
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Callable, TypeVar

from loguru import logger

T = TypeVar("T")

_pools: dict[str, ProcessPoolExecutor] = {}
_lock = threading.Lock()

_POOL_DEFAULTS: dict[str, int] = {
    "ocr": 1,
    "tools": 2,
    "ui": 2,
    "rag": 1,
}


def get_process_pool(name: str, *, max_workers: int | None = None) -> ProcessPoolExecutor:
    with _lock:
        pool = _pools.get(name)
        if pool is None:
            workers = max_workers if max_workers is not None else _POOL_DEFAULTS.get(name, 2)
            ctx = multiprocessing.get_context("spawn")
            pool = ProcessPoolExecutor(max_workers=workers, mp_context=ctx)
            _pools[name] = pool
            logger.debug("[process] 已创建进程池 {} (max_workers={})", name, workers)
        return pool


def run_in_process(
    func: Callable[..., T],
    /,
    *args: Any,
    pool: str = "tools",
    timeout: float | None = None,
    max_workers: int | None = None,
    **kwargs: Any,
) -> T:
    """在指定进程池中执行可 pickle 的顶层函数。"""
    executor = get_process_pool(pool, max_workers=max_workers)
    future = executor.submit(func, *args, **kwargs)
    return future.result(timeout=timeout)


def shutdown_process_pools(*, wait: bool = False) -> None:
    global _pools
    with _lock:
        names = list(_pools.keys())
    for name in names:
        with _lock:
            pool = _pools.pop(name, None)
        if pool is None:
            continue
        try:
            pool.shutdown(wait=wait, cancel_futures=not wait)
        except Exception as exc:
            logger.debug("[process] 关闭进程池 {}: {}", name, exc)


atexit.register(shutdown_process_pools)
