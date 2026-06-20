"""OCR 子进程执行，避免 Paddle 推理阻塞主进程。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from src.infra.process_executor import run_in_process

_OCR_PROGRESS_TEXT = "正在识别中…"


def ocr_progress_text() -> str:
    return _OCR_PROGRESS_TEXT


def _ocr_worker(path: str) -> dict[str, Any]:
    from src.ui.ocr.core import ocr_image_path

    return ocr_image_path(path)


def ocr_image_path_in_process(path: str | Path, *, timeout: float | None = 180) -> dict[str, Any]:
    """在独立进程中运行 OCR，主进程仅等待 Future 结果。"""
    image_path = str(Path(path))
    try:
        return run_in_process(_ocr_worker, image_path, pool="ocr", timeout=timeout)
    except Exception as exc:
        logger.warning("[ocr] 子进程识别失败: {}", exc)
        return {"ok": False, "error": str(exc), "engine": "ocr-worker"}


def shutdown_ocr_pool(*, wait: bool = False) -> None:
    from src.infra.process_executor import shutdown_process_pools

    shutdown_process_pools(wait=wait)
