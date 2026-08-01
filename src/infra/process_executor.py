"""共享 ProcessPoolExecutor（spawn），供 OCR / Agent 工具 / UI 重任务使用。"""

from __future__ import annotations

import atexit
import multiprocessing
import threading
import time
from concurrent.futures import ProcessPoolExecutor, Future
from typing import Any, Callable, TypeVar

from loguru import logger

T = TypeVar("T")

_pools: dict[str, ProcessPoolExecutor] = {}
_lock = threading.Lock()
_shutdown_event = threading.Event()

_POOL_DEFAULTS: dict[str, int] = {
    "ocr": 1,
    "tools": 2,
    "ui": 2,
    "rag": 1,
}


def get_process_pool(name: str, *, max_workers: int | None = None) -> ProcessPoolExecutor:
    """获取指定名称的进程池，若不存在则创建。"""
    with _lock:
        if _shutdown_event.is_set():
            logger.warning("[process] 已进入关闭阶段，拒绝创建新进程池: {}", name)
            raise RuntimeError("进程池服务已关闭")
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


def _cancel_pending(futures: list[Future]) -> int:
    """取消所有未完成的任务。"""
    cancelled = 0
    for future in futures:
        if not future.done():
            if future.cancel():
                cancelled += 1
    return cancelled


def shutdown_process_pools(*, wait: bool = False, timeout: float = 10.0) -> None:
    """安全关闭所有进程池，避免竞态条件。"""
    _shutdown_event.set()
    with _lock:
        pools_to_shutdown = list(_pools.items())
        _pools.clear()
    if not pools_to_shutdown:
        return

    logger.info("[process] 开始关闭 {} 个进程池", len(pools_to_shutdown))
    start_time = time.time()

    for name, pool in pools_to_shutdown:
        try:
            if not wait:
                pool.shutdown(wait=False, cancel_futures=True)
                logger.debug("[process] 进程池 {} 已异步关闭", name)
            else:
                elapsed = time.time() - start_time
                remaining = max(0.0, timeout - elapsed)
                if remaining <= 0:
                    logger.warning("[process] 进程池 {} 关闭超时，强制取消", name)
                    pool.shutdown(wait=False, cancel_futures=True)
                    continue
                pool.shutdown(wait=True, cancel_futures=False)
                logger.debug("[process] 进程池 {} 已同步关闭", name)
        except Exception as exc:
            logger.warning("[process] 关闭进程池 {} 失败: {}", name, exc)

    elapsed = time.time() - start_time
    logger.info("[process] 所有进程池关闭完成，耗时 {:.2f}s", elapsed)


def _warmup_ping() -> str:
    """可 pickle 的预热探针。"""
    return "ok"


def warmup_process_pools(
    pools: tuple[str, ...] = ("tools", "ui", "rag"),
    *,
    timeout: float = 90.0,
) -> None:
    """空闲时预热 spawn 子进程，降低首轮工具/RAG 冷启动。"""
    if _shutdown_event.is_set():
        return
    for name in pools:
        try:
            run_in_process(_warmup_ping, pool=name, timeout=timeout)
            logger.info("[process] 进程池已预热: {}", name)
        except Exception as exc:
            logger.debug("[process] 预热 {} 失败: {}", name, exc)


atexit.register(shutdown_process_pools)
