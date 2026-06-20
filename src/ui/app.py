from __future__ import annotations

import json
import queue
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

import webview
from loguru import logger

from src.agent.graph import AgentGraphBundle, build_agent_graph
from src.agent.runner import AgentRunner, StreamEvent
from src.infra.config import ensure_data_dirs, load_app_config, load_merged_providers, save_api_key
from src.infra.paths import PROJECT_ROOT
from src.infra.user_settings import has_stored_api_key, persist_provider_choice
from src.llm.factory import create_llm
from src.llm.providers import ProviderConfig
from src.memory.rag import get_knowledge_stats, ingest_files, set_rag_provider
from src.memory.search_cache import SearchCache
from src.ui.clipboard import copy_to_clipboard as sys_copy_to_clipboard
from src.ui.font_prefs import (
    build_font_variables,
    get_font_prefs,
    list_font_catalog,
    persist_font_prefs,
)
from src.ui.input_compose import compose_user_message, save_temp_image_b64
from src.ui.speech_win import get_voice_info as speech_voice_info
from src.ui.speech_win import is_supported as voice_is_supported
from src.ui.speech_win import recognize_once
from src.ui.theme_loader import (
    build_css_variables,
    get_theme_prefs,
    list_theme_catalog,
    persist_theme_prefs,
)
from src.ui.web_bridge import WebChatBridge

WEB_DIR = PROJECT_ROOT / "web"
WEB_INDEX = WEB_DIR / "index.html"


class AppApi:
    """暴露给 pywebview JS 的 API。"""

    def __init__(self, controller: AssistantController) -> None:
        self._ctrl = controller

    def get_initial_state(self) -> dict[str, Any]:
        return self._ctrl.build_initial_state()

    def get_settings_data(self) -> dict[str, Any]:
        return self._ctrl.build_settings_data()

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._ctrl.save_settings(payload)

    def send_message(self, payload: dict[str, Any] | str) -> bool:
        if isinstance(payload, str):
            payload = {"text": payload, "attachments": []}
        return self._ctrl.send_message(payload)

    def pick_input_image(self) -> dict[str, Any]:
        return self._ctrl.pick_input_image()

    def pick_input_file(self) -> dict[str, Any]:
        return self._ctrl.pick_input_file()

    def save_pasted_image(self, data_b64: str) -> dict[str, Any]:
        return save_temp_image_b64(data_b64)

    def get_voice_info(self) -> dict[str, Any]:
        return self._ctrl.get_voice_info()

    def start_voice_input(self) -> dict[str, Any]:
        return self._ctrl.start_voice_input()

    def stop_agent(self) -> None:
        self._ctrl.stop_agent()

    def new_session(self) -> None:
        self._ctrl.new_session()

    def approval_response(self, approved: bool) -> None:
        self._ctrl.approval_response(approved)

    def get_knowledge_stats(self) -> dict[str, str]:
        return self._ctrl.knowledge_stats_text()

    def import_knowledge(self, kind: str) -> dict[str, Any]:
        return self._ctrl.import_knowledge(kind)

    def copy_to_clipboard(self, text: str) -> bool:
        return sys_copy_to_clipboard(text)


class AssistantController:
    """Agent 与 Web UI 控制器。"""

    def __init__(self) -> None:
        ensure_data_dirs()
        self.app_cfg = load_app_config()
        self._current_provider_name, self._providers = load_merged_providers()
        self._current_provider = self._providers[self._current_provider_name]
        self._theme_id, self._appearance = get_theme_prefs()
        self._font_id = get_font_prefs()

        self._window: webview.Window | None = None
        self.chat = WebChatBridge(self._get_window)
        self._thread_id = str(uuid.uuid4())
        self._running = False
        self._graph_bundle: AgentGraphBundle | None = None
        self._awaiting_approval = False
        self._search_cache = SearchCache()
        self._turn_user_query = ""
        self._turn_search_query = ""
        self._turn_used_web_search = False
        self._turn_search_ok = False
        self._collecting_assistant = False
        self._poll_stop = threading.Event()
        self._voice_running = False

        self._init_agent()

    def attach_window(self, window: webview.Window) -> None:
        self._window = window

    def _get_window(self) -> webview.Window | None:
        return self._window

    def _status_text(self, suffix: str = "") -> str:
        p = self._current_provider
        base = f"模型: {self._current_provider_name} / {p.model}  |  会话: {self._thread_id[:8]}..."
        return f"{base}  |  {suffix}" if suffix else base

    def _ui_variables(self) -> dict[str, str]:
        vars_ = build_css_variables(self._theme_id, self._appearance)
        vars_.update(build_font_variables(self._font_id))
        return vars_

    def build_initial_state(self) -> dict[str, Any]:
        app = self.app_cfg.get("app", {})
        return {
            "title": app.get("title", "个人助理 Agent"),
            "theme_variables": self._ui_variables(),
            "theme_id": self._theme_id,
            "appearance": self._appearance,
            "font_id": self._font_id,
            "status_text": self._status_text("就绪"),
            "welcome": "欢迎使用个人助理 Agent。Enter 发送，Shift+Enter 换行。",
            "composer_meta": {
                "session_short": self._thread_id[:8],
                "voice_supported": voice_is_supported(),
            },
        }

    def _provider_payload(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for name, p in self._providers.items():
            out[name] = {
                "model": p.model,
                "base_url": p.base_url or "",
                "temperature": p.temperature,
                "has_api_key": has_stored_api_key(p.api_key_env),
            }
        return out

    def build_settings_data(self) -> dict[str, Any]:
        return {
            "theme_catalog": list_theme_catalog(),
            "theme_id": self._theme_id,
            "appearance": self._appearance,
            "font_catalog": list_font_catalog(),
            "font_id": self._font_id,
            "current_provider": self._current_provider_name,
            "provider_names": list(self._providers.keys()),
            "providers": self._provider_payload(),
        }

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        theme_id = payload.get("theme_id") or "default"
        appearance = payload.get("appearance") or "dark"
        font_id = payload.get("font_id") or get_font_prefs()
        persist_theme_prefs(theme_id, appearance)
        persist_font_prefs(font_id)
        self._theme_id = theme_id
        self._appearance = appearance
        self._font_id = get_font_prefs()
        vars_ = self._ui_variables()

        name = payload.get("provider") or self._current_provider_name
        if name not in self._providers:
            return {"ok": False, "error": "无效的 Provider"}

        p = self._providers[name]
        p.model = (payload.get("model") or p.model).strip() or p.model
        p.base_url = (payload.get("base_url") or p.base_url or "").strip()
        p.temperature = float(payload.get("temperature", p.temperature))

        api_key = (payload.get("api_key") or "").strip()
        if api_key and p.api_key_env:
            save_api_key(p.api_key_env, api_key)
        elif not has_stored_api_key(p.api_key_env):
            return {"ok": False, "error": "请填写 API Key"}

        persist_provider_choice(name, p)
        self._current_provider_name = name
        self._current_provider = p
        self._providers[name] = p
        self._init_agent()
        self.chat.append_system(f"已切换 Provider: {name} / {p.model}")

        return {
            "ok": True,
            "theme_variables": vars_,
            "status_text": self._status_text("就绪"),
        }

    def _init_agent(self) -> None:
        try:
            if self._graph_bundle:
                self._graph_bundle.close()
            set_rag_provider(self._current_provider)
            llm = create_llm(self._current_provider)
            ckpt = Path(self.app_cfg["paths"]["checkpoints"]) / "agent.db"
            self._graph_bundle = build_agent_graph(llm, ckpt)
            self.runner = AgentRunner(graph=self._graph_bundle.graph)
            self.chat.set_status(self._status_text("就绪"))
        except Exception as exc:
            logger.exception("Agent 初始化失败")
            self.chat.append_error(f"Agent 初始化失败: {exc}")
            self.runner = AgentRunner(graph=None)

    def send_message(self, payload: dict[str, Any]) -> bool:
        if self._running:
            return False

        composed = compose_user_message(
            str(payload.get("text", "")),
            payload.get("attachments") or [],
        )
        if not composed.get("ok"):
            self.chat.append_error(composed.get("error", "无法发送空消息"))
            return False

        message = composed["message"]
        for warn in composed.get("errors") or []:
            self.chat.append_system(warn)

        if not self.runner.graph:
            self.chat.append_error("Agent 未就绪，请检查 LLM 配置与 API Key。")
            return False

        self.chat.append_user(message)

        cached = self._search_cache.lookup(message)
        if cached:
            self._deliver_cached_search(message, cached)
            return False

        self._start_agent_turn(message)
        return True

    def pick_input_image(self) -> dict[str, Any]:
        window = self._get_window()
        if window is None:
            return {"ok": False, "paths": []}
        file_types = ("图片 (*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif)", "All files (*.*)")
        try:
            paths = window.create_file_dialog(
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
            paths = window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
            return {"ok": True, "paths": list(paths or [])}
        except Exception as exc:
            return {"ok": False, "paths": [], "error": str(exc)}

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

    def _start_agent_turn(self, text: str) -> None:
        self._turn_user_query = text
        self._turn_search_query = ""
        self._turn_used_web_search = False
        self._turn_search_ok = False
        self._collecting_assistant = False
        self._running = True
        self.chat.set_running(True)
        self.chat.set_status(self._status_text("思考中…"))
        self.runner.run_async(text, self._thread_id)

    def _deliver_cached_search(self, user_query: str, response: str) -> None:
        self.chat.append_assistant_complete(response, from_cache=True)
        self.chat.set_status(self._status_text("搜索缓存命中"))

    def stop_agent(self) -> None:
        if self._running:
            self.runner.stop()
            self.chat.append_system("已请求停止。")

    def new_session(self) -> None:
        self._thread_id = str(uuid.uuid4())
        self.chat.clear()
        self.chat.append_system(f"新会话已创建: {self._thread_id[:8]}...")
        self.chat.set_status(self._status_text())
        window = self._get_window()
        if window is not None:
            short = self._thread_id[:8]
            try:
                window.evaluate_js(
                    f"document.getElementById('meta-session')&&(document.getElementById('meta-session').textContent='会话 {short}')"
                )
            except Exception:
                pass

    def approval_response(self, approved: bool) -> None:
        if not self._awaiting_approval:
            return
        self._awaiting_approval = False
        self.runner.resume_after_approval(approved)
        self.chat.append_system("已批准操作，正在执行..." if approved else "已拒绝操作。")

    def knowledge_stats_text(self) -> dict[str, str]:
        stats = get_knowledge_stats()
        backend = "本地" if stats["embedding_backend"] == "local" else "API"
        text = (
            f"已索引文档: {stats['document_count']} 个\n"
            f"向量块数: {stats['chunk_count']}\n"
            f"索引状态: {'已建立' if stats['has_index'] else '未建立'}\n"
            f"Embedding: {backend} ({stats['embedding_model']})"
        )
        return {"text": text}

    def import_knowledge(self, kind: str) -> dict[str, Any]:
        window = self._get_window()
        if window is None:
            return {"log": "窗口未就绪"}

        file_types = (
            "文档 (*.txt;*.md;*.pdf;*.docx)",
            "All files (*.*)",
        )
        try:
            if kind == "folder":
                paths = window.create_file_dialog(webview.FOLDER_DIALOG)
            else:
                paths = window.create_file_dialog(
                    webview.OPEN_DIALOG,
                    allow_multiple=True,
                    file_types=file_types,
                )
        except Exception as exc:
            return {"log": f"选择失败: {exc}"}

        if not paths:
            return {"log": "已取消"}

        path_list = [Path(p) for p in paths]
        try:
            file_count, chunk_count = ingest_files(path_list, self._current_provider)
            log = f"完成：{file_count} 个文件，{chunk_count} 个文本块"
            self.chat.append_system(log)
            return {"log": log, **self.knowledge_stats_text()}
        except Exception as exc:
            logger.exception("知识库导入失败")
            return {"log": f"导入失败: {exc}"}

    def _maybe_save_search_cache(self, response: str) -> None:
        if self._turn_used_web_search and response.strip():
            self._search_cache.save_async(
                self._turn_user_query,
                self._turn_search_query or self._turn_user_query,
                response,
                search_ok=self._turn_search_ok,
                finished=True,
            )
        self._turn_user_query = ""
        self._turn_search_query = ""
        self._turn_used_web_search = False
        self._turn_search_ok = False
        self._collecting_assistant = False

    def _reset_turn_state(self) -> None:
        self._turn_user_query = ""
        self._turn_search_query = ""
        self._turn_used_web_search = False
        self._turn_search_ok = False
        self._collecting_assistant = False

    def _handle_approval(self, payload: dict) -> None:
        if self._awaiting_approval:
            return
        self._awaiting_approval = True
        description = payload.get("description", "确认执行敏感操作？")
        self.chat.show_approval(description)

    def poll_agent_events(self) -> None:
        if not (self.runner and self.runner.graph):
            return

        batch: list[StreamEvent] = []
        while True:
            try:
                batch.append(self.runner.event_queue.get_nowait())
            except queue.Empty:
                break

        skip_until: int | None = None
        for i, event in enumerate(batch):
            if event.kind == "tool_call" and event.payload.get("name") == "web_search":
                skip_until = i
                break

        waiting_approval = False
        still_running = True
        for i, event in enumerate(batch):
            if skip_until is not None and i < skip_until and event.kind == "token":
                continue
            if event.kind == "approval_required":
                waiting_approval = True
            if not self._handle_agent_event(event):
                still_running = False
                break

        if still_running:
            if waiting_approval:
                still_running = True
            else:
                t = self.runner._thread
                still_running = t is not None and t.is_alive()
            if not still_running and self._running:
                self._running = False
                self.chat.set_running(False)

    def _handle_agent_event(self, event: StreamEvent) -> bool:
        if event.kind == "token":
            if self._collecting_assistant:
                pass
            self.chat.append_token(event.payload)
        elif event.kind == "tool_call":
            p = event.payload
            if p["name"] == "web_search":
                self.chat.reset_assistant_for_tool()
                self._turn_used_web_search = True
                self._turn_search_query = str(p.get("args", {}).get("query", ""))
                self._collecting_assistant = False
            self.chat.append_tool_call(p["name"], p.get("args", {}))
        elif event.kind == "tool_result":
            p = event.payload
            if p["name"] == "web_search":
                raw = str(p.get("content", ""))
                self._turn_search_ok = (
                    "搜索失败" not in raw
                    and "未找到" not in raw
                    and "未返回有效" not in raw
                )
                self._collecting_assistant = True
            self.chat.append_tool_result(p["name"], p["content"])
        elif event.kind == "approval_required":
            self._handle_approval(event.payload)
        elif event.kind == "done":
            response = self.chat.assistant_stream_buffer
            self.chat.end_assistant()
            self._maybe_save_search_cache(response)
            self._running = False
            self.chat.set_running(False)
            self.chat.set_status(self._status_text("就绪"))
            return False
        elif event.kind == "error":
            self.chat.append_error(event.payload)
            self._reset_turn_state()
            self._running = False
            self.chat.set_running(False)
            return False
        elif event.kind == "stopped":
            self._reset_turn_state()
            self._running = False
            self.chat.set_running(False)
            return False
        return True


def _poll_loop(controller: AssistantController, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            controller.poll_agent_events()
        except Exception:
            logger.exception("事件轮询异常")
        stop.wait(0.05)


def run_app() -> None:
    import os

    if not WEB_INDEX.exists():
        raise FileNotFoundError(f"Web UI 未找到: {WEB_INDEX}")

    controller = AssistantController()
    api = AppApi(controller)
    app_cfg = controller.app_cfg.get("app", {})
    w = int(app_cfg.get("window_width", 1100))
    h = int(app_cfg.get("window_height", 720))
    title = app_cfg.get("title", "个人助理 Agent")
    webview_debug = os.environ.get("AGENT_WEBVIEW_DEBUG", "").lower() in ("1", "true", "yes")
    if webview_debug:
        logger.info("[voice] WebView debug 已开启（F12 可开开发者工具）")

    window = webview.create_window(
        title,
        url=WEB_INDEX.as_uri(),
        js_api=api,
        width=w,
        height=h,
        min_size=(800, 560),
    )
    controller.attach_window(window)

    stop = controller._poll_stop
    poll_thread = threading.Thread(
        target=_poll_loop,
        args=(controller, stop),
        daemon=True,
        name="agent-event-poll",
    )
    poll_thread.start()

    logger.info("WebView 窗口启动中…")
    try:
        webview.start(debug=webview_debug)
    finally:
        stop.set()
        if controller._graph_bundle:
            controller._graph_bundle.close()
