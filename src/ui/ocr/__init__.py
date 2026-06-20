"""图片 OCR。"""
import importlib
import sys

from src.ui.ocr.core import (
    _extract_paddle_text,
    _ocr_engine_name,
    _paddle_available,
    _paddle_missing_message,
    _paddle_ocr_version,
    _use_paddle_ocr,
    _use_winrt_ocr,
    ocr_image_path,
)
from src.ui.ocr.worker import ocr_image_path_in_process, ocr_progress_text, shutdown_ocr_pool

__all__ = [
    "_extract_paddle_text",
    "_ocr_engine_name",
    "_paddle_available",
    "_paddle_missing_message",
    "_paddle_ocr_version",
    "_use_paddle_ocr",
    "_use_winrt_ocr",
    "importlib",
    "ocr_image_path",
    "ocr_image_path_in_process",
    "ocr_progress_text",
    "shutdown_ocr_pool",
    "sys",
]

importlib = importlib
sys = sys
