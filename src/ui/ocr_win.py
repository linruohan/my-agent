"""Windows 本地 OCR（WinRT OcrEngine，无需 paddlepaddle）。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from loguru import logger

_OCR_LANG_TAGS = ("zh-Hans-CN", "zh-CN", "en-US")


def is_winrt_ocr_supported() -> bool:
    if sys.platform != "win32":
        return False
    try:
        from winrt.windows.media.ocr import OcrEngine

        if OcrEngine.try_create_from_user_profile_languages() is not None:
            return True
        from winrt.windows.globalization import Language

        for tag in _OCR_LANG_TAGS:
            if OcrEngine.is_language_supported(Language(tag)):
                return True
        return bool(list(OcrEngine.available_recognizer_languages))
    except ImportError:
        return False
    except Exception as exc:
        logger.debug("[ocr-win] 探测失败: {}", exc)
        return False


def _create_engine():
    from winrt.windows.globalization import Language
    from winrt.windows.media.ocr import OcrEngine

    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is not None:
        return engine
    for tag in _OCR_LANG_TAGS:
        if OcrEngine.is_language_supported(Language(tag)):
            engine = OcrEngine.try_create_from_language(Language(tag))
            if engine is not None:
                return engine
    langs = list(OcrEngine.available_recognizer_languages)
    if langs:
        return OcrEngine.try_create_from_language(langs[0])
    return None


async def _ocr_file_async(path: Path) -> str:
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.storage import FileAccessMode, StorageFile

    file = await StorageFile.get_file_from_path_async(str(path.resolve()))
    stream = await file.open_async(FileAccessMode.READ)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()

    engine = _create_engine()
    if engine is None:
        raise RuntimeError(
            "未找到 OCR 语言包。请在「设置 → 时间和语言 → 语言」中安装中文，"
            "并在「可选功能」中安装「中文 OCR」。"
        )

    result = await engine.recognize_async(bitmap)
    return (result.text or "").strip()


def ocr_image_path_win(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": f"图片不存在: {p}"}
    if not is_winrt_ocr_supported():
        return {
            "ok": False,
            "error": "WinRT OCR 不可用，请安装: pip install winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging winrt-Windows.Storage winrt-Windows.Storage.Streams",
            "engine": "winrt-ocr",
        }

    try:
        from winrt.runtime import ApartmentType, init_apartment

        init_apartment(ApartmentType.SINGLE_THREADED)
        text = asyncio.run(_ocr_file_async(p))
    except ImportError:
        return {
            "ok": False,
            "error": "缺少 WinRT OCR 依赖，请运行: pip install winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging winrt-Windows.Storage winrt-Windows.Storage.Streams",
            "engine": "winrt-ocr",
        }
    except Exception as exc:
        logger.exception("[ocr-win] 识别失败")
        return {"ok": False, "error": str(exc), "engine": "winrt-ocr"}

    logger.info("[ocr-win] 识别完成 len={}", len(text))
    return {
        "ok": True,
        "text": text or "(未识别到文字)",
        "engine": "winrt-ocr",
    }
