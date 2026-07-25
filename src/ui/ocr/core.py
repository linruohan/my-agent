"""图片 OCR：默认 PaddleOCR；Windows 上 Paddle 失败时回退 WinRT。"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from loguru import logger

_paddle_engine: Any = None


def _configure_paddle_env() -> None:
    """规避 PaddlePaddle 3.3 + oneDNN/PIR 在 CPU 上的已知崩溃。"""
    os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
    os.environ.setdefault("FLAGS_enable_pir_api", "0")
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


_configure_paddle_env()


def _ocr_engine_name() -> str:
    return os.environ.get("AGENT_OCR_ENGINE", "paddle").strip().lower()


def _paddle_available() -> bool:
    return importlib.util.find_spec("paddle") is not None


def _use_winrt_ocr() -> bool:
    return _ocr_engine_name() in ("winrt", "local", "windows")


def _use_paddle_ocr() -> bool:
    return _ocr_engine_name() in ("", "paddle", "paddleocr")


def _paddle_missing_message() -> str:
    py = f"{sys.version_info.major}.{sys.version_info.minor}"
    if sys.version_info >= (3, 14):
        return (
            f"PaddleOCR 需要 paddlepaddle，但 PyPI 尚无 Python {py} 的 wheel。"
            "请改用 WinRT OCR（AGENT_OCR_ENGINE=winrt），或使用 Python 3.11–3.13 安装: "
            "pip install -e \".[input]\""
        )
    return "缺少 paddlepaddle，请运行: pip install paddleocr paddlepaddle"


def _paddle_ocr_version() -> str:
    return os.environ.get("AGENT_OCR_PADDLE_VERSION", "PP-OCRv6").strip()


def _get_paddle_engine() -> Any:
    global _paddle_engine
    if _paddle_engine is None:
        if not _paddle_available():
            raise RuntimeError(_paddle_missing_message())
        _configure_paddle_env()
        version = _paddle_ocr_version()
        logger.info(
            "首次 OCR：正在加载 PaddleOCR {} 模型（约数十秒，仅第一次较慢）…",
            version,
        )
        from paddleocr import PaddleOCR  # type: ignore[import-untyped]

        _paddle_engine = PaddleOCR(
            ocr_version=version,
            lang="ch",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
        )
        logger.info("PaddleOCR {} 模型已就绪", version)
    return _paddle_engine


def _legacy_line_text(item: Any) -> str | None:
    if not isinstance(item, (list, tuple)) or len(item) < 2:
        return None
    text_part = item[1]
    if isinstance(text_part, (list, tuple)) and text_part and isinstance(text_part[0], str):
        return str(text_part[0])
    if isinstance(text_part, str):
        return text_part
    return None


def _extract_paddle_text(raw: Any) -> list[str]:
    """兼容 PaddleOCR 2.x 与 3.x 返回结构。"""
    lines: list[str] = []
    if not raw:
        return lines

    pages = raw if isinstance(raw, list) else [raw]
    for page in pages:
        if page is None:
            continue

        rec_texts: Any = None
        if isinstance(page, dict):
            rec_texts = page.get("rec_texts")
        elif hasattr(page, "get"):
            try:
                rec_texts = page.get("rec_texts")
            except Exception:
                rec_texts = None
        if rec_texts is None and hasattr(page, "rec_texts"):
            rec_texts = page.rec_texts
        if rec_texts is None and hasattr(page, "json"):
            try:
                payload = page.json() if callable(page.json) else page.json
                if isinstance(payload, dict):
                    rec_texts = payload.get("rec_texts")
            except Exception:
                from loguru import logger

                logger.debug("OCR 页面 json 解析跳过", exc_info=True)

        if rec_texts:
            for text in rec_texts:
                if text:
                    lines.append(str(text))
            continue

        if isinstance(page, (list, tuple)):
            direct = _legacy_line_text(page)
            if direct:
                lines.append(direct)
                continue
            for item in page:
                text = _legacy_line_text(item)
                if text:
                    lines.append(text)
    return lines


def _ocr_image_path_paddle(path: Path) -> dict[str, Any]:
    try:
        engine = _get_paddle_engine()
        raw = engine.predict(str(path))
    except ImportError:
        return {"ok": False, "error": _paddle_missing_message(), "engine": "paddleocr"}
    except Exception as exc:
        msg = str(exc)
        if "paddlepaddle" in msg.lower() or "paddle_static" in msg.lower():
            return {"ok": False, "error": _paddle_missing_message(), "engine": "paddleocr"}
        return {"ok": False, "error": msg, "engine": "paddleocr"}

    lines = _extract_paddle_text(raw)
    text = "\n".join(lines).strip()
    return {
        "ok": True,
        "text": text or "(未识别到文字)",
        "engine": "paddleocr",
        "model": _paddle_ocr_version(),
    }


def _try_winrt_ocr(path: Path) -> dict[str, Any] | None:
    if sys.platform != "win32":
        return None
    from src.ui.ocr.win import is_winrt_ocr_supported, ocr_image_path_win

    if not is_winrt_ocr_supported():
        return None
    return ocr_image_path_win(path)


def _winrt_unavailable_error() -> dict[str, Any]:
    return {
        "ok": False,
        "error": (
            "WinRT OCR 不可用。请安装: pip install winrt-Windows.Media.Ocr "
            "winrt-Windows.Graphics.Imaging winrt-Windows.Storage winrt-Windows.Storage.Streams"
        ),
        "engine": "winrt-ocr",
    }


def ocr_image_path(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": f"图片不存在: {p}"}

    if _use_winrt_ocr() and not _use_paddle_ocr():
        winrt = _try_winrt_ocr(p)
        if winrt and winrt.get("ok"):
            return winrt
        if _paddle_available():
            logger.warning("[ocr] WinRT OCR 不可用或失败，回退 PaddleOCR")
            return _ocr_image_path_paddle(p)
        return winrt if winrt is not None else _winrt_unavailable_error()

    if _paddle_available():
        result = _ocr_image_path_paddle(p)
        if result.get("ok"):
            return result
        winrt = _try_winrt_ocr(p)
        if winrt and winrt.get("ok"):
            logger.info("[ocr] PaddleOCR 失败，已改用 WinRT OCR")
            return winrt
        return result

    winrt = _try_winrt_ocr(p)
    if winrt is not None:
        return winrt

    return {"ok": False, "error": _paddle_missing_message()}
