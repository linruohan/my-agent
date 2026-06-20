"""Windows 11 语音识别（WinRT / winrt 包，SpeechRecognizer）。"""

from __future__ import annotations

import asyncio
import sys
import threading
from collections.abc import Coroutine
from datetime import timedelta
from typing import Any

from loguru import logger

# 全局：WinRT 专用线程 + 事件循环（避免 pywebview 后台线程 apartment 问题）
_winrt_loop: asyncio.AbstractEventLoop | None = None
_winrt_thread: threading.Thread | None = None
_winrt_ready = threading.Event()


def is_supported() -> bool:
    if sys.platform != "win32":
        logger.debug("[voice] is_supported=False platform={}", sys.platform)
        return False
    try:
        _import_winrt()
        logger.debug("[voice] is_supported=True winrt import ok")
        return True
    except ImportError as exc:
        logger.debug("[voice] is_supported=False import error: {}", exc)
        return False


def _import_winrt() -> None:
    from winrt.windows.globalization import Language  # noqa: F401
    from winrt.windows.media.speechrecognition import (  # noqa: F401
        SpeechRecognitionResultStatus,
        SpeechRecognizer,
    )


def _status_label(status: int) -> str:
    try:
        from winrt.windows.media.speechrecognition import SpeechRecognitionResultStatus

        for name in dir(SpeechRecognitionResultStatus):
            if name.isupper() and getattr(SpeechRecognitionResultStatus, name) == status:
                return name
    except Exception:
        pass
    return str(status)


def _ensure_winrt_thread() -> asyncio.AbstractEventLoop:
    global _winrt_loop, _winrt_thread

    if _winrt_loop is not None and _winrt_loop.is_running():
        logger.debug("[voice] WinRT 线程已运行 thread={}", _winrt_thread and _winrt_thread.name)
        return _winrt_loop

    logger.info("[voice] 启动 WinRT 专用线程…")

    def _runner() -> None:
        global _winrt_loop
        from winrt.runtime import ApartmentType, init_apartment

        logger.debug("[voice] WinRT 线程 runner 开始 tid={}", threading.get_ident())
        init_apartment(ApartmentType.SINGLE_THREADED)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _winrt_loop = loop
        _winrt_ready.set()
        logger.info("[voice] WinRT 事件循环就绪")
        loop.run_forever()
        logger.debug("[voice] WinRT 事件循环已退出")

    _winrt_ready.clear()
    _winrt_thread = threading.Thread(target=_runner, name="winrt-speech", daemon=True)
    _winrt_thread.start()
    if not _winrt_ready.wait(timeout=10):
        logger.error("[voice] WinRT 线程 10s 内未就绪")
        raise RuntimeError("WinRT 语音线程启动失败")
    if _winrt_loop is None:
        logger.error("[voice] WinRT 线程就绪但 loop 为空")
        raise RuntimeError("WinRT 语音线程启动失败")
    logger.debug("[voice] WinRT 线程启动完成 alive={}", _winrt_thread.is_alive())
    return _winrt_loop


def _run_coro(coro: Coroutine[Any, Any, Any]) -> Any:
    loop = _ensure_winrt_thread()
    logger.debug("[voice] 提交协程到 WinRT 线程 loop={}", loop)
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        result = future.result(timeout=120)
        logger.debug("[voice] 协程完成")
        return result
    except Exception:
        logger.exception("[voice] 协程执行失败")
        raise


async def _create_recognizer():
    from winrt.windows.globalization import Language
    from winrt.windows.media.speechrecognition import SpeechRecognizer

    for tag in ("zh-CN", "zh-Hans-CN", "zh-TW", "en-US"):
        try:
            logger.debug("[voice] 尝试创建 SpeechRecognizer lang={}", tag)
            rec = SpeechRecognizer(Language(tag))
            logger.info("[voice] SpeechRecognizer 已创建 lang={}", tag)
            return rec
        except Exception as exc:
            logger.debug("[voice] SpeechRecognizer lang={} 失败: {}", tag, exc)
            continue
    logger.warning("[voice] 指定语言均失败，使用系统默认 SpeechRecognizer")
    return SpeechRecognizer()


def _join_unique_phrases(phrases: list[str]) -> str:
    """合并识别片段，去除 WinRT 连续识别产生的相邻重复/渐进 refinements。"""
    out: list[str] = []
    for raw in phrases:
        p = (raw or "").strip()
        if not p:
            continue
        if out and out[-1] == p:
            continue
        # 后一条是前一条的扩展（同一句话的 refinement）
        if out and p.startswith(out[-1]) and len(p) > len(out[-1]):
            out[-1] = p
            continue
        if out and out[-1].startswith(p):
            continue
        out.append(p)
    return " ".join(out).strip()


async def _recognize_dictation(recognizer) -> tuple[str, str | None]:
    """单次听写（recognize_async），返回 (text, cancel_flag)。"""
    from winrt.windows.media.speechrecognition import SpeechRecognitionResultStatus

    logger.info("[voice] 开始单次听写 recognize_async")
    result = await recognizer.recognize_async()
    status = _status_label(result.status)
    logger.debug("[voice] recognize_async status={}", status)
    if result.status == SpeechRecognitionResultStatus.SUCCESS:
        text = (result.text or "").strip()
        if text:
            logger.info("[voice] 听写文本: {}", text)
        return text, None
    if result.status == SpeechRecognitionResultStatus.USER_CANCELED:
        logger.info("[voice] 用户取消听写")
        return "", "canceled"
    logger.debug("[voice] recognize_async 无有效文本 status={}", status)
    return "", None


async def _recognize_once_async(*, listen_seconds: float = 18.0) -> dict[str, Any]:
    from winrt.windows.media.speechrecognition import SpeechRecognitionResultStatus

    logger.info("[voice] _recognize_once_async 开始 listen_seconds={}", listen_seconds)
    recognizer = await _create_recognizer()
    lang = recognizer.current_language.language_tag if recognizer.current_language else "unknown"
    logger.debug("[voice] 当前识别语言={}", lang)

    timeouts = recognizer.timeouts
    if timeouts is not None:
        timeouts.initial_silence_timeout = timedelta(seconds=10)
        timeouts.end_silence_timeout = timedelta(seconds=2)
        timeouts.babble_timeout = timedelta(seconds=0)

    logger.debug("[voice] 编译语音约束…")
    compile_result = await recognizer.compile_constraints_async()
    compile_status = _status_label(compile_result.status)
    logger.debug("[voice] 约束编译结果 status={}", compile_status)
    if compile_result.status != SpeechRecognitionResultStatus.SUCCESS:
        recognizer.close()
        return {
            "ok": False,
            "error": f"语音约束编译失败: {compile_status}",
            "language": lang,
        }

    text = ""
    mode = "dictation"
    try:
        text, cancel = await _recognize_dictation(recognizer)
        if cancel == "canceled":
            recognizer.close()
            return {"ok": True, "text": "", "canceled": True, "language": lang, "mode": mode}
        if not text:
            mode = "ui"
            logger.info("[voice] 单次听写无结果，回退 recognize_with_ui_async")
            ui_result = await recognizer.recognize_with_ui_async()
            ui_status = _status_label(ui_result.status)
            logger.debug("[voice] UI 识别结果 status={}", ui_status)
            if ui_result.status == SpeechRecognitionResultStatus.SUCCESS:
                text = (ui_result.text or "").strip()
                if text:
                    logger.info("[voice] UI 识别文本: {}", text)
            elif ui_result.status == SpeechRecognitionResultStatus.USER_CANCELED:
                recognizer.close()
                logger.info("[voice] 用户取消 UI 识别")
                return {"ok": True, "text": "", "canceled": True, "language": lang, "mode": mode}
            elif ui_result.status != SpeechRecognitionResultStatus.SUCCESS:
                recognizer.close()
                return {
                    "ok": False,
                    "error": f"语音识别失败: {ui_status}",
                    "language": lang,
                    "mode": mode,
                }
    finally:
        recognizer.close()

    if text:
        logger.info("[voice] 识别成功 mode={} len={} text={!r}", mode, len(text), text[:80])
        return {"ok": True, "text": text, "language": lang, "mode": mode}

    logger.warning("[voice] 识别结束但无文本 mode={} lang={}", mode, lang)
    return {
        "ok": False,
        "error": "未识别到语音。请确认：设置→隐私→麦克风已允许桌面应用；系统已安装中文语音包。",
        "language": lang,
        "mode": mode,
    }


def recognize_once(*, listen_seconds: float = 18.0) -> dict[str, Any]:
    """单次语音听写（Win11 WinRT SpeechRecognizer）。"""
    logger.info("[voice] recognize_once 调用 listen_seconds={} thread={}", listen_seconds, threading.current_thread().name)
    if not is_supported():
        logger.warning("[voice] recognize_once 不支持当前平台/依赖")
        return {
            "ok": False,
            "error": "语音输入仅支持 Windows，且需安装 winrt 包",
        }

    try:
        result = _run_coro(_recognize_once_async(listen_seconds=listen_seconds))
        logger.info("[voice] recognize_once 返回 ok={} error={}", result.get("ok"), result.get("error", ""))
        return result
    except ImportError:
        logger.exception("[voice] WinRT 依赖缺失")
        return {
            "ok": False,
            "error": "缺少 WinRT 依赖，请运行: pip install winrt-runtime winrt-Windows.Media.SpeechRecognition winrt-Windows.Globalization winrt-Windows.Foundation",
        }
    except Exception as exc:
        logger.exception("[voice] recognize_once 异常")
        return {"ok": False, "error": str(exc)}


def get_voice_info() -> dict[str, Any]:
    logger.debug("[voice] get_voice_info 调用 thread={}", threading.current_thread().name)
    if sys.platform != "win32":
        info = {"supported": False, "error": "语音输入仅支持 Windows", "platform": sys.platform}
        logger.debug("[voice] get_voice_info -> {}", info)
        return info
    if not is_supported():
        info = {
            "supported": False,
            "error": "未安装 WinRT 语音依赖（winrt-Windows.Media.SpeechRecognition）",
            "platform": sys.platform,
        }
        logger.debug("[voice] get_voice_info -> {}", info)
        return info
    try:
        loop = _ensure_winrt_thread()

        async def _lang() -> str:
            r = await _create_recognizer()
            tag = r.current_language.language_tag if r.current_language else ""
            r.close()
            return tag

        lang = asyncio.run_coroutine_threadsafe(_lang(), loop).result(timeout=10)
        info = {"supported": True, "platform": sys.platform, "language": lang, "engine": "winrt"}
        logger.info("[voice] get_voice_info -> supported lang={}", lang)
        return info
    except Exception as exc:
        logger.exception("[voice] get_voice_info 探测语言失败")
        return {"supported": True, "platform": sys.platform, "engine": "winrt", "language": "", "warn": str(exc)}
