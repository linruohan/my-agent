"""应用启动后台预热（进程池 / Embedding），不阻塞 UI。"""

from __future__ import annotations

import os
import threading

from loguru import logger


def _warmup_enabled() -> bool:
    return os.environ.get("AGENT_WARMUP", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _run_warmup() -> None:
    from src.infra.process_executor import warmup_process_pools
    from src.memory.embeddings import create_local_embeddings
    from src.memory.rag import _rag_config

    warmup_process_pools()
    model = str(_rag_config().get("local_embedding_model", "BAAI/bge-small-zh-v1.5"))
    create_local_embeddings(model)
    logger.info("[warmup] Embedding 模型已就绪: {}", model)


def schedule_startup_warmup() -> None:
    """在后台线程预热，失败仅记日志。"""
    if not _warmup_enabled():
        logger.debug("[warmup] 已禁用（AGENT_WARMUP=0）")
        return

    def _worker() -> None:
        try:
            _run_warmup()
            logger.info("[warmup] 启动预热完成")
        except Exception:
            logger.debug("[warmup] 启动预热失败", exc_info=True)

    threading.Thread(target=_worker, daemon=True, name="startup-warmup").start()
