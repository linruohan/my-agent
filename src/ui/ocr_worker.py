"""兼容层：请使用 src.ui.ocr.worker。"""
import sys
from pathlib import Path
from typing import Any

from src.infra.process_executor import run_in_process
from src.ui.ocr.worker import _ocr_worker, ocr_progress_text, shutdown_ocr_pool

__all__ = [
    "_ocr_worker",
    "ocr_image_path_in_process",
    "ocr_progress_text",
    "run_in_process",
    "shutdown_ocr_pool",
    "sys",
]

sys = sys


def ocr_image_path_in_process(path: str | Path, *, timeout: float | None = 180) -> dict[str, Any]:
    image_path = str(Path(path))
    return run_in_process(_ocr_worker, image_path, pool="ocr", timeout=timeout)
