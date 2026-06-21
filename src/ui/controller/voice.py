"""语音输入与文件选择。"""

from __future__ import annotations

import json
import threading
from typing import Any

import webview
from loguru import logger

from src.ui.file_dialog import create_file_dialog_safe
from src.ui.speech import (
    ensure_speech_privacy_ready,
    get_voice_info as speech_voice_info,
    is_supported as voice_is_supported,
    open_speech_privacy_settings,
    recognize_once,
)


class VoiceMixin:
    """语音输入与系统语音设置。"""

    def get_voice_info(self) -> dict[str, Any]:
        logger.debug("[voice] AppApi.get_voice_info")
        info = speech_voice_info()
        logger.debug("[voice] AppApi.get_voice_info -> {}", info)
        return info

    def start_voice_input(self) -> dict[str, Any]:
        logger.info("[voice] AppApi.start_voice_input voice_running={}", self._voice_running)
        if self._voice_running:
            logger.warning("[voice] 拒绝：已有识别任务进行中")
            return {"ok": False, "error": "语音识别进行中"}
        if not voice_is_supported():
            logger.warning("[voice] 拒绝：平台/依赖不支持")
            return {"ok": False, "error": "仅 Windows 支持语音输入"}

        privacy_block = ensure_speech_privacy_ready()
        if privacy_block is not None:
            logger.warning("[voice] 语音隐私未就绪，已引导打开系统设置")
            return privacy_block

        def worker() -> None:
            logger.info("[voice] worker 线程开始 tid={}", threading.get_ident())
            result: dict[str, Any]
            try:
                result = recognize_once(listen_seconds=18.0)
            except Exception as exc:
                logger.exception("[voice] worker 语音识别异常")
                result = {"ok": False, "error": str(exc)}
            self._voice_running = False
            logger.info(
                "[voice] worker 完成 ok={} text_len={} error={}",
                result.get("ok"),
                len(result.get("text") or ""),
                result.get("error", ""),
            )
            window = self._get_window()
            if window is None:
                logger.error("[voice] window 为空，无法回传 UI")
                return
            payload = json.dumps(result, ensure_ascii=False)
            logger.debug("[voice] evaluate_js payload={}", payload[:500])
            try:
                window.evaluate_js(f"window.Composer.onVoiceResult({payload})")
                logger.debug("[voice] evaluate_js 已调用")
            except Exception:
                logger.exception("[voice] 语音结果回传 UI 失败")

        self._voice_running = True
        threading.Thread(target=worker, daemon=True, name="voice-input").start()
        logger.info("[voice] voice-input 后台线程已启动")
        return {"ok": True}

    def open_speech_settings(self) -> dict[str, Any]:
        opened = open_speech_privacy_settings()
        return {"ok": opened, "settings_opened": opened}


class FilesMixin:
    """附件与知识库文件选择。"""

    def pick_input_image(self) -> dict[str, Any]:
        window = self._get_window()
        if window is None:
            return {"ok": False, "paths": []}
        file_types = ("图片 (*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif)", "All files (*.*)")
        try:
            paths = create_file_dialog_safe(
                window,
                webview.OPEN_DIALOG,
                allow_multiple=True,
                file_types=file_types,
            )
            return {"ok": True, "paths": list(paths or [])}
        except Exception as exc:
            return {"ok": False, "paths": [], "error": str(exc)}

    def pick_input_file(self) -> dict[str, Any]:
        window = self._get_window()
        if window is None:
            return {"ok": False, "paths": []}
        try:
            paths = create_file_dialog_safe(window, webview.OPEN_DIALOG, allow_multiple=True)
            return {"ok": True, "paths": list(paths or [])}
        except Exception as exc:
            return {"ok": False, "paths": [], "error": str(exc)}
