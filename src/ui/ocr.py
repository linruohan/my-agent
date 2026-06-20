"""PaddleOCR 图片文字识别。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_ocr_engine: Any = None


def _get_engine() -> Any:
    global _ocr_engine
    if _ocr_engine is None:
        from loguru import logger

        logger.info("首次 OCR：正在加载 PaddleOCR 模型（约数十秒，仅第一次较慢）…")
        from paddleocr import PaddleOCR  # type: ignore[import-untyped]

        _ocr_engine = PaddleOCR(use_angle_cls=True, lang="ch")
        logger.info("PaddleOCR 模型已就绪")
    return _ocr_engine


def ocr_image_path(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": f"图片不存在: {p}"}
    try:
        engine = _get_engine()
        raw = engine.ocr(str(p), cls=True)
    except ImportError:
        return {"ok": False, "error": "缺少 PaddleOCR，请运行: pip install paddleocr paddlepaddle"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    lines: list[str] = []
    for block in raw or []:
        if not block:
            continue
        for item in block:
            if item and len(item) >= 2 and item[1]:
                lines.append(str(item[1][0]))
    text = "\n".join(lines).strip()
    return {"ok": True, "text": text or "(未识别到文字)"}
