"""Windows 语音识别：默认 SAPI 本地听写；可选 WinRT 在线听写。"""

from __future__ import annotations

import asyncio
import os
import sys
import threading
from collections.abc import Coroutine
from datetime import timedelta
from typing import Any

from loguru import logger

from src.ui.speech import sapi as speech_sapi

# WinRT: 0x80045509 — 未接受语音隐私策略 / 在线语音识别未开启
SPEECH_PRIVACY_WINERROR = -2147199735
SPEECH_PRIVACY_HINT = (
    "系统「在线语音识别」未开启。请前往：设置 → 隐私和安全性 → 语音 → "
    "开启「在线语音识别」，完成后再次点击话筒。"
)
SPEECH_SETTINGS_URIS = (
    "ms-settings:privacy-speech",
    "ms-settings:privacy-speechtyping",
    "ms-settings:speech",
)


def _voice_engine() -> str:
    return os.environ.get("AGENT_VOICE_ENGINE", "local").strip().lower()


def _use_local_sapi() -> bool:
    return _voice_engine() in ("", "local", "sapi", "offline")


def _winrt_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        _import_winrt()
        return True
    except ImportError:
        return False

# 全局：WinRT 专用线程 + 事件循环（避免 pywebview 后台线程 apartment 问题）
_winrt_loop: asyncio.AbstractEventLoop | None = None
_winrt_thread: threading.Thread | None = None
_winrt_ready = threading.Event()


def is_supported() -> bool:
    if sys.platform != "win32":
        logger.debug("[voice] is_supported=False platform={}", sys.platform)
        return False
    if _use_local_sapi() and speech_sapi.is_sapi_supported():
        logger.debug("[voice] is_supported=True engine=sapi-local")
        return True
    if _voice_engine() in ("winrt", "online") and _winrt_available():
        logger.debug("[voice] is_supported=True engine=winrt")
        return True
    logger.debug("[voice] is_supported=False no engine")
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


def _is_speech_privacy_error(exc: BaseException) -> bool:
    if isinstance(exc, OSError) and getattr(exc, "winerror", None) == SPEECH_PRIVACY_WINERROR:
        return True
    msg = str(exc).lower()
    return "speech privacy policy" in msg or "privacy policy was not accepted" in msg


def _privacy_not_ready_result(*, settings_opened: bool) -> dict[str, Any]:
    hint = SPEECH_PRIVACY_HINT
    if settings_opened:
        hint = f"{hint}（已打开系统设置页）"
    return {
        "ok": False,
        "error": hint,
        "needs_speech_settings": True,
        "settings_opened": settings_opened,
    }


def open_speech_privacy_settings() -> bool:
    """打开语音相关设置（本地模式优先语言/麦克风，在线模式打开隐私页）。"""
    if _use_local_sapi():
        return speech_sapi.open_local_speech_settings()
    import os

    for uri in SPEECH_SETTINGS_URIS:
        try:
            os.startfile(uri)  # noqa: S606
            logger.info("[voice] 已打开系统语音设置: {}", uri)
            return True
        except OSError as exc:
            logger.debug("[voice] 打开设置失败 {}: {}", uri, exc)
    logger.warning("[voice] 无法打开系统语音设置页")
    return False


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


async def _verify_speech_privacy_ready() -> bool:
    """探测语音隐私策略是否已接受（未接受时 recognize_async 会立即失败）。"""
    recognizer = await _create_recognizer()
    try:
        from winrt.windows.media.speechrecognition import SpeechRecognitionResultStatus

        compile_result = await recognizer.compile_constraints_async()
        if compile_result.status != SpeechRecognitionResultStatus.SUCCESS:
            logger.debug("[voice] 隐私探测：约束编译非 SUCCESS，跳过探测")
            return True

        timeouts = recognizer.timeouts
        if timeouts is not None:
            timeouts.initial_silence_timeout = timedelta(milliseconds=300)
            timeouts.end_silence_timeout = timedelta(milliseconds=200)
            timeouts.babble_timeout = timedelta(seconds=0)

        logger.debug("[voice] 隐私探测：调用 recognize_async")
        await recognizer.recognize_async()
    except OSError as exc:
        if _is_speech_privacy_error(exc):
            logger.warning("[voice] 语音隐私策略未接受: {}", exc)
            return False
        raise
    finally:
        recognizer.close()
    return True


async def _recognize_dictation(recognizer) -> tuple[str, str | None]:
    """单次听写（recognize_async），返回 (text, cancel_flag)。"""
    from winrt.windows.media.speechrecognition import SpeechRecognitionResultStatus

    logger.info("[voice] 开始单次听写 recognize_async")
    try:
        result = await recognizer.recognize_async()
    except OSError as exc:
        if _is_speech_privacy_error(exc):
            logger.warning("[voice] recognize_async 语音隐私未接受")
            return "", "privacy_denied"
        raise
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
        if cancel == "privacy_denied":
            recognizer.close()
            opened = open_speech_privacy_settings()
            return _privacy_not_ready_result(settings_opened=opened)
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


def ensure_speech_privacy_ready() -> dict[str, Any] | None:
    """识别前检查。本地 SAPI 无需在线语音；WinRT 需在线语音识别。"""
    if _use_local_sapi():
        return None
    if not _winrt_available():
        return None
    try:
        ready = _run_coro(_verify_speech_privacy_ready())
    except Exception as exc:
        if _is_speech_privacy_error(exc):
            ready = False
        else:
            logger.exception("[voice] 语音隐私探测异常")
            return {"ok": False, "error": str(exc)}
    if ready:
        return None
    opened = open_speech_privacy_settings()
    return _privacy_not_ready_result(settings_opened=opened)


def recognize_once(*, listen_seconds: float = 18.0) -> dict[str, Any]:
    """单次语音听写。默认本地 SAPI，无需开启在线语音识别。"""
    logger.info(
        "[voice] recognize_once engine={} listen_seconds={} thread={}",
        _voice_engine(),
        listen_seconds,
        threading.current_thread().name,
    )
    if not is_supported():
        return {
            "ok": False,
            "error": "语音输入仅支持 Windows，且需 pywin32（本地）或 winrt 包（在线）",
        }

    if _use_local_sapi():
        if speech_sapi.is_sapi_supported():
            return speech_sapi.recognize_once_sapi(listen_seconds=listen_seconds)
        return {
            "ok": False,
            "error": "本地 SAPI 不可用，请运行: pip install pywin32",
            "engine": "sapi-local",
        }

    return _recognize_once_winrt(listen_seconds=listen_seconds)


def _recognize_once_winrt(*, listen_seconds: float = 18.0) -> dict[str, Any]:
    """WinRT 在线听写（需开启系统「在线语音识别」）。"""
    if not _winrt_available():
        return {
            "ok": False,
            "error": "WinRT 语音不可用，请安装 winrt 包或改用本地模式（默认）",
        }

    try:
        result = _run_coro(_recognize_once_async(listen_seconds=listen_seconds))
        logger.info("[voice] recognize_once winrt 返回 ok={} error={}", result.get("ok"), result.get("error", ""))
        return result
    except ImportError:
        logger.exception("[voice] WinRT 依赖缺失")
        return {
            "ok": False,
            "error": "缺少 WinRT 依赖，请运行: pip install winrt-runtime winrt-Windows.Media.SpeechRecognition winrt-Windows.Globalization winrt-Windows.Foundation",
        }
    except Exception as exc:
        if _is_speech_privacy_error(exc):
            opened = open_speech_privacy_settings()
            return _privacy_not_ready_result(settings_opened=opened)
        logger.exception("[voice] recognize_once 异常")
        return {"ok": False, "error": str(exc)}


def get_voice_info() -> dict[str, Any]:
    logger.debug("[voice] get_voice_info engine={}", _voice_engine())
    if sys.platform != "win32":
        info = {"supported": False, "error": "语音输入仅支持 Windows", "platform": sys.platform}
        return info

    if _use_local_sapi() and speech_sapi.is_sapi_supported():
        return speech_sapi.get_sapi_voice_info()

    if not _winrt_available():
        return {
            "supported": False,
            "error": "未安装本地语音 pywin32，也未安装 WinRT 语音依赖",
            "platform": sys.platform,
        }

    try:
        loop = _ensure_winrt_thread()

        async def _lang() -> str:
            r = await _create_recognizer()
            tag = r.current_language.language_tag if r.current_language else ""
            r.close()
            return tag

        lang = asyncio.run_coroutine_threadsafe(_lang(), loop).result(timeout=10)
        info = {
            "supported": True,
            "platform": sys.platform,
            "language": lang,
            "engine": "winrt",
            "online_required": True,
        }
        logger.info("[voice] get_voice_info -> winrt lang={}", lang)
        return info
    except Exception as exc:
        logger.exception("[voice] get_voice_info 探测语言失败")
        return {
            "supported": True,
            "platform": sys.platform,
            "engine": "winrt",
            "language": "",
            "online_required": True,
            "warn": str(exc),
        }
