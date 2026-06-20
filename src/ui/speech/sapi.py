"""Windows 本地语音识别（SAPI 听写，设备端，无需「在线语音识别」）。"""

from __future__ import annotations

import sys
import threading
import time
from typing import Any

from loguru import logger

_sapi_lock = threading.Lock()

LOCAL_SPEECH_HINT = (
    "本地语音识别未就绪。请确认：① 设置→隐私→麦克风允许桌面应用；"
    "② 设置→时间和语言→语音，已安装中文语音包。"
)
SPEECH_LANGUAGE_SETTINGS_URIS = (
    "ms-settings:speech",
    "ms-settings:regionlanguage",
    "ms-settings:privacy-microphone",
)


def is_sapi_supported() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        try:
            win32com.client.Dispatch("SAPI.SpSharedRecognizer")
            return True
        finally:
            pythoncom.CoUninitialize()
    except Exception as exc:
        logger.debug("[voice-sapi] 不可用: {}", exc)
        return False


def open_local_speech_settings() -> bool:
    import os

    for uri in SPEECH_LANGUAGE_SETTINGS_URIS:
        try:
            os.startfile(uri)  # noqa: S606
            logger.info("[voice-sapi] 已打开设置: {}", uri)
            return True
        except OSError as exc:
            logger.debug("[voice-sapi] 打开设置失败 {}: {}", uri, exc)
    return False


def _recognize_sapi_blocking(*, listen_seconds: float) -> dict[str, Any]:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    phrases: list[str] = []
    error: str | None = None

    try:
        listener = win32com.client.Dispatch("SAPI.SpSharedRecognizer")
        context = listener.CreateRecoContext()
        grammar = context.CreateGrammar()

        events_base = win32com.client.getevents("SAPI.SpSharedRecoContext")

        class _ContextEvents(events_base):  # type: ignore[misc,valid-type]
            def OnRecognition(
                self,
                StreamNumber: int,
                StreamPosition: int,
                RecognitionType: int,
                Result: Any,
            ) -> None:
                try:
                    new_result = win32com.client.Dispatch(Result)
                    text = (new_result.PhraseInfo.GetText() or "").strip()
                    if text:
                        logger.info("[voice-sapi] 识别片段: {}", text)
                        phrases.append(text)
                except Exception:
                    logger.exception("[voice-sapi] OnRecognition 回调异常")

            def OnRecognitionForOtherContext(self, StreamNumber: int, StreamPosition: int) -> None:
                pass

        _ContextEvents(context)

        grammar.DictationLoad()
        grammar.DictationSetState(1)
        logger.info("[voice-sapi] 本地听写已开始 listen_seconds={}", listen_seconds)

        deadline = time.monotonic() + listen_seconds
        while time.monotonic() < deadline:
            pythoncom.PumpWaitingMessages()
            time.sleep(0.05)

        grammar.DictationSetState(0)
    except Exception as exc:
        logger.exception("[voice-sapi] 识别异常")
        error = str(exc)
    finally:
        pythoncom.CoUninitialize()

    text = " ".join(phrases).strip()
    if text:
        return {
            "ok": True,
            "text": text,
            "language": "local",
            "mode": "sapi-dictation",
            "engine": "sapi-local",
        }

    if error:
        opened = open_local_speech_settings()
        hint = f"{LOCAL_SPEECH_HINT} 详情: {error}"
        if opened:
            hint = f"{hint}（已打开语音/语言设置）"
        return {"ok": False, "error": hint, "engine": "sapi-local", "needs_speech_settings": True}

    return {
        "ok": False,
        "error": "未识别到语音。请对着麦克风说话，说完后稍等片刻。",
        "engine": "sapi-local",
        "mode": "sapi-dictation",
    }


def recognize_once_sapi(*, listen_seconds: float = 18.0) -> dict[str, Any]:
    """SAPI 本地听写（单次）。"""
    if not is_sapi_supported():
        return {
            "ok": False,
            "error": "本地 SAPI 语音不可用，请安装 pywin32（pip install pywin32）",
            "engine": "sapi-local",
        }

    logger.info("[voice-sapi] recognize_once_sapi 开始")
    with _sapi_lock:
        result = _recognize_sapi_blocking(listen_seconds=listen_seconds)
    logger.info("[voice-sapi] 完成 ok={} text_len={}", result.get("ok"), len(result.get("text") or ""))
    return result


def get_sapi_voice_info() -> dict[str, Any]:
    if sys.platform != "win32":
        return {"supported": False, "error": "语音输入仅支持 Windows", "platform": sys.platform}
    if not is_sapi_supported():
        return {
            "supported": False,
            "error": "本地 SAPI 不可用，请安装 pywin32",
            "platform": sys.platform,
            "engine": "sapi-local",
        }
    return {
        "supported": True,
        "platform": sys.platform,
        "language": "local",
        "engine": "sapi-local",
        "online_required": False,
    }
