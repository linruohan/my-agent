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
from src.infra.user_settings import has_stored_api_key, load_user_settings, persist_provider_choice, save_user_settings
from src.llm.factory import create_llm
from src.llm.providers import ProviderConfig
from src.memory.rag import get_knowledge_stats, set_rag_provider
from src.memory.rag_worker import ingest_files_in_process
from src.memory.search_cache import SearchCache, handle_cache_command
from src.ui.clipboard import copy_to_clipboard as sys_copy_to_clipboard
from src.ui.open_local import check_local_paths as sys_check_local_paths
from src.ui.open_local import open_local_path as sys_open_local_path
from src.ui.font_prefs import (
    build_font_variables,
    get_font_prefs,
    list_font_catalog,
    persist_font_prefs,
)
from src.ui.input import (
    build_image_previews,
    compose_ocr_message,
    compose_user_message,
    format_ocr_reply,
    has_sendable_content,
    save_temp_image_b64,
    append_history,
    list_history,
    INTENT_LINK,
    INTENT_OCR,
    INTENT_SEARCH,
    INTENT_SLASH_CACHE,
    INTENT_SLASH_NOTE,
    INTENT_SLASH_OCR,
    INTENT_SLASH_SKILL,
    INTENT_SLASH_TASK,
    INTENT_SLASH_WEATHER,
    INTENT_WEATHER,
    InputIntent,
    resolve_input_intent,
)
from src.ui.skill import build_slash_catalog, get_skill_dirs, load_skill_prompt, run_skill
from src.ui.link import run_link_summarize_turn
from src.ui.message_utils import normalize_user_message
from src.ui.ocr import ocr_progress_text
from src.ui.speech import (
    ensure_speech_privacy_ready,
    get_voice_info as speech_voice_info,
    is_supported as voice_is_supported,
    open_speech_privacy_settings,
    recognize_once,
)
from src.ui.session_store import SessionStore
from src.infra.process_executor import shutdown_process_pools
from src.ui.theme_loader import (
    build_css_variables,
    get_theme_prefs,
    list_theme_catalog,
    persist_theme_prefs,
)
from src.tools.note import NoteStore, handle_note_command
from src.tools.task import TaskReminderService, TaskStore, handle_task_command, migrate_legacy_todos_json
from src.tools.tool_worker import invoke_tool_in_process
from src.ui.search_turn import run_web_search_turn
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

    def read_image_data_url(self, path: str) -> dict[str, Any]:
        from src.ui.input import image_to_data_url

        return image_to_data_url(path)

    def get_voice_info(self) -> dict[str, Any]:
        return self._ctrl.get_voice_info()

    def start_voice_input(self) -> dict[str, Any]:
        return self._ctrl.start_voice_input()

    def open_speech_settings(self) -> dict[str, Any]:
        return self._ctrl.open_speech_settings()

    def stop_agent(self) -> None:
        self._ctrl.stop_agent()

    def new_session(self) -> dict[str, Any]:
        return self._ctrl.new_session()

    def list_sessions(self) -> dict[str, Any]:
        return self._ctrl.list_sessions_api()

    def switch_session(self, session_id: str) -> dict[str, Any]:
        return self._ctrl.switch_session(session_id)

    def delete_session(self, session_id: str) -> dict[str, Any]:
        return self._ctrl.delete_session(session_id)

    def rename_session(self, session_id: str, title: str) -> dict[str, Any]:
        return self._ctrl.rename_session(session_id, title)

    def get_slash_catalog(self) -> list[dict[str, Any]]:
        return self._ctrl.get_slash_catalog()

    def get_input_history(self) -> list[str]:
        return self._ctrl.get_input_history()

    def save_input_history(self, text: str) -> None:
        self._ctrl.save_input_history(text)

    def approval_response(self, approved: bool) -> None:
        self._ctrl.approval_response(approved)

    def get_knowledge_stats(self) -> dict[str, str]:
        return self._ctrl.knowledge_stats_text()

    def import_knowledge(self, kind: str) -> dict[str, Any]:
        return self._ctrl.import_knowledge(kind)

    def copy_to_clipboard(self, text: str) -> bool:
        return sys_copy_to_clipboard(text)

    def open_local_path(self, path: str) -> dict[str, Any]:
        return sys_open_local_path(path)

    def check_local_paths(self, paths: list[str]) -> dict[str, bool]:
        return sys_check_local_paths(paths)


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
        self._session_store = SessionStore()
        sessions = self._session_store.list_sessions()
        active = sessions[0] if sessions else self._session_store.create_session("当前会话")
        self._session_id = active.id
        self._thread_id = active.thread_id
        self.chat = WebChatBridge(self._get_window, on_event=self._on_chat_event)
        self._note_store = NoteStore()
        self._task_store = TaskStore()
        migrate_legacy_todos_json(self._task_store)
        self._task_reminder = TaskReminderService(self._task_store)
        self._task_reminder.start()
        self._running = False
        self._graph_bundle: AgentGraphBundle | None = None
        self._llm: Any = None
        self._awaiting_approval = False
        self._search_cache = SearchCache()
        self._turn_user_query = ""
        self._turn_search_query = ""
        self._turn_used_web_search = False
        self._turn_search_ok = False
        self._collecting_assistant = False
        self._poll_stop = threading.Event()
        self._voice_running = False
        self._compose_busy = False
        self._compose_cancel = threading.Event()
        self._skip_persist_events = False

        self._init_agent()

    def _on_chat_event(self, event: dict[str, Any]) -> None:
        if self._skip_persist_events:
            return
        if event.get("type") in ("user", "assistant_end", "meta"):
            self._session_store.append_event(self._session_id, event)

    def attach_window(self, window: webview.Window) -> None:
        self._window = window

    def _get_window(self) -> webview.Window | None:
        return self._window

    def get_slash_catalog(self) -> list[dict[str, Any]]:
        return build_slash_catalog()

    def get_input_history(self) -> list[str]:
        return list_history()

    def save_input_history(self, text: str) -> None:
        append_history(text)

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
        settings = load_user_settings()
        ui = settings.get("ui", {}) or {}
        return {
            "title": app.get("title", "个人助理 Agent"),
            "theme_variables": self._ui_variables(),
            "theme_id": self._theme_id,
            "appearance": self._appearance,
            "font_id": self._font_id,
            "status_text": self._status_text("就绪"),
            "welcome": "欢迎使用个人助理 Agent。Enter 发送，Shift+Enter 换行。输入 / 查看命令。",
            "composer_meta": {
                "session_short": self._thread_id[:8],
                "voice_supported": voice_is_supported(),
            },
            "sessions": [
                {"id": s.id, "title": s.title, "active": s.id == self._session_id}
                for s in self._session_store.list_sessions()
            ],
            "slash_catalog": build_slash_catalog(),
            "input_history": list_history(),
            "skill_dirs": [str(p) for p in get_skill_dirs()],
            "session_events": self._session_store.load_events(self._session_id),
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
        settings = load_user_settings()
        ui = settings.get("ui", {}) or {}
        skill_dirs = ui.get("skill_dirs") or settings.get("skill_dirs") or []
        if isinstance(skill_dirs, str):
            skill_dirs = [skill_dirs]
        return {
            "theme_catalog": list_theme_catalog(),
            "theme_id": self._theme_id,
            "appearance": self._appearance,
            "font_catalog": list_font_catalog(),
            "font_id": self._font_id,
            "current_provider": self._current_provider_name,
            "provider_names": list(self._providers.keys()),
            "providers": self._provider_payload(),
            "skill_dirs": "\n".join(str(x) for x in skill_dirs),
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

        skill_dirs_raw = (payload.get("skill_dirs") or "").strip()
        skill_dirs = [line.strip() for line in skill_dirs_raw.splitlines() if line.strip()]
        settings = load_user_settings()
        ui = settings.setdefault("ui", {})
        ui["skill_dirs"] = skill_dirs
        save_user_settings(settings)
        self._providers[name] = p
        self._init_agent()
        self.chat.set_status(self._status_text("设置已更新"))

        return {
            "ok": True,
            "theme_variables": vars_,
            "status_text": self._status_text("设置已更新"),
        }

    def _init_agent(self) -> None:
        try:
            if self._graph_bundle:
                self._graph_bundle.close()
            set_rag_provider(self._current_provider)
            self._llm = create_llm(self._current_provider)
            ckpt = Path(self.app_cfg["paths"]["checkpoints"]) / "agent.db"
            self._graph_bundle = build_agent_graph(self._llm, ckpt)
            self.runner = AgentRunner(graph=self._graph_bundle.graph)
            self.chat.set_status(self._status_text("就绪"))
        except Exception as exc:
            logger.exception("Agent 初始化失败")
            self.chat.append_error(f"Agent 初始化失败: {exc}")
            self.runner = AgentRunner(graph=None)

    def _is_busy(self) -> bool:
        return self._running or self._compose_busy

    def send_message(self, payload: dict[str, Any]) -> bool:
        if self._is_busy():
            return False

        text = str(payload.get("text", ""))
        attachments = list(payload.get("attachments") or [])

        if not has_sendable_content(text, attachments):
            self.chat.append_error("请输入内容或添加附件")
            return False

        display_text = normalize_user_message(text)
        images = build_image_previews(attachments)
        self.chat.append_user(display_text, images=images)
        append_history(display_text)

        self._compose_cancel.clear()
        self._compose_busy = True
        self.chat.set_running(True)

        threading.Thread(
            target=self._process_send_message,
            args=(text, attachments),
            daemon=True,
            name="compose-send",
        ).start()
        return True

    @staticmethod
    def _should_use_search_pipeline(
        composed: dict[str, Any],
        attachments: list[dict[str, Any]],
    ) -> bool:
        """已由 resolve_input_intent 替代，保留供测试/兼容。"""
        if composed.get("ocr_only"):
            return False
        if any(att.get("type") in ("file", "link") for att in attachments):
            return False
        user_text = str(composed.get("user_text") or "").strip()
        message = str(composed.get("message") or "").strip()
        if attachments and message != user_text:
            return False
        return bool(user_text or message)

    def _lookup_search_cache(self, *queries: str) -> str | None:
        seen: set[str] = set()
        for query in queries:
            q = (query or "").strip()
            if not q or q in seen:
                continue
            seen.add(q)
            hit = self._search_cache.lookup(q)
            if hit:
                return hit
        return None

    def _process_send_message(self, text: str, attachments: list[dict[str, Any]]) -> None:
        try:
            if self._compose_cancel.is_set():
                return

            intent = resolve_input_intent(text, attachments, llm=self._llm)
            logger.info("[intent] kind={} reason={}", intent.kind, intent.reason)

            if intent.kind == INTENT_SLASH_NOTE:
                self._handle_slash_note(intent)
                return

            if intent.kind == INTENT_SLASH_CACHE:
                self._handle_slash_cache(intent)
                return

            if intent.kind == INTENT_SLASH_TASK:
                self._handle_slash_task(intent)
                return

            if intent.kind == INTENT_SLASH_SKILL:
                self._handle_slash_skill(intent, text)
                return

            if intent.kind in (INTENT_OCR, INTENT_SLASH_OCR):
                self._handle_ocr_intent(text, attachments, intent)
                return

            if intent.kind in (INTENT_WEATHER, INTENT_SLASH_WEATHER):
                self._handle_weather_intent(intent, text)
                return

            if intent.kind == INTENT_LINK:
                self._start_link_summarize_turn(intent)
                return

            search_query = (intent.search_query or normalize_user_message(text or "")).strip()
            if intent.kind == INTENT_SEARCH and search_query and not attachments:
                cached = self._lookup_search_cache(search_query)
                if cached:
                    self._deliver_cached_search(search_query, cached)
                    return

            if intent.kind == INTENT_SEARCH and search_query:
                self._start_search_turn(search_query)
                return

            # Agent 路径：按需 OCR / 抓取链接
            has_images = any(att.get("type") == "image" for att in attachments)
            ocr_progress = False
            if has_images:
                ocr_progress = True
                self.chat.begin_assistant_progress(ocr_progress_text())

            if self._compose_cancel.is_set():
                return

            composed = compose_user_message(text, attachments)
            if self._compose_cancel.is_set():
                return

            if not composed.get("ok"):
                if ocr_progress:
                    self.chat.append_assistant_complete(f"识别失败：{composed.get('error', '消息处理失败')}")
                else:
                    self.chat.append_error(composed.get("error", "消息处理失败"))
                return

            for warn in composed.get("errors") or []:
                self.chat.append_system(warn)

            if self._compose_cancel.is_set():
                return

            message = composed["message"]
            if not self.runner.graph:
                if ocr_progress:
                    self.chat.append_assistant_complete("Agent 未就绪，请检查 LLM 配置与 API Key。")
                else:
                    self.chat.append_error("Agent 未就绪，请检查 LLM 配置与 API Key。")
                return

            if ocr_progress:
                self.chat.reset_assistant_for_tool()

            if self._compose_cancel.is_set():
                return

            self._start_agent_turn(message)
        finally:
            if not self._running:
                self._compose_busy = False
                if not self._compose_cancel.is_set():
                    self.chat.set_running(False)

    def _handle_slash_note(self, intent: InputIntent) -> None:
        args = (intent.slash_args or intent.note_content or "").strip()
        if not args:
            self.chat.append_error("用法：/note add <标题> <内容> | list | <关键字> | rm <id>")
            self.chat.set_status(self._status_text("就绪"))
            return
        try:
            result = handle_note_command(args, self._note_store)
            self.chat.append_assistant_complete(result)
            self.chat.set_status(self._status_text("就绪"))
        except ValueError as exc:
            self.chat.append_error(str(exc))
            self.chat.set_status(self._status_text("就绪"))
        except Exception as exc:
            logger.exception("笔记命令失败")
            self.chat.append_error(f"笔记命令失败: {exc}")

    def _handle_slash_cache(self, intent: InputIntent) -> None:
        try:
            result = handle_cache_command(intent.slash_args, self._search_cache)
            self.chat.append_assistant_complete(result)
            self.chat.set_status(self._status_text("就绪"))
        except Exception as exc:
            logger.exception("缓存命令失败")
            self.chat.append_error(f"缓存命令失败: {exc}")

    def _handle_slash_task(self, intent: InputIntent) -> None:
        try:
            result = handle_task_command(intent.slash_args, self._task_store)
            fmt = "markdown"
            self.chat.append_assistant_complete(result, content_format=fmt)
            self.chat.set_status(self._status_text("就绪"))
        except Exception as exc:
            logger.exception("任务命令失败")
            self.chat.append_error(f"任务命令失败: {exc}")

    def _handle_slash_skill(self, intent: InputIntent, text: str) -> None:
        skill_name = intent.skill_name or intent.slash_cmd
        user_part = (intent.slash_args or "").strip()

        self.chat.begin_assistant_progress(f"正在执行 Skill: {skill_name}…")
        self.chat.set_tool_status(f"⚙ 正在按 SKILL.md 执行 {skill_name}…", accent="info")

        def worker() -> None:
            try:
                self.chat.set_tool_status(f"🧠 正在识别 Skill 意图: {skill_name}…", accent="info")
                result = run_skill(skill_name, user_part, llm=self._llm)
                if result.intent_reason and result.intent_reason not in {"raw_cli", "heuristic"}:
                    self.chat.append_tool_call(
                        "parse_skill_intent",
                        {"skill": skill_name, "reason": result.intent_reason},
                    )
                self.chat.set_tool_status(f"⚙ 正在执行 Skill: {skill_name}…", accent="info")
                if result.command:
                    self.chat.append_tool_call(
                        "run_skill",
                        {"skill": skill_name, "cmd": result.command},
                    )
                if result.ok:
                    self.chat.append_assistant_complete(result.output)
                    self.chat.set_status(self._status_text("就绪"))
                    return

                if result.fallback_agent:
                    prompt = load_skill_prompt(skill_name)
                    if not prompt:
                        self.chat.append_error(result.error or f"未找到 Skill：{skill_name}")
                        self.chat.set_status(self._status_text("就绪"))
                        return
                    self.chat.reset_assistant_for_tool()
                    message = (
                        f"【Skill: {skill_name}】\n\n{prompt}\n\n---\n\n"
                        f"用户请求：{user_part or '请按 Skill 说明执行'}"
                    )
                    self._start_agent_turn(message)
                    return

                detail = result.output or result.error or "Skill 执行失败"
                self.chat.append_assistant_complete(f"Skill 执行失败：{result.error}\n\n{detail}")
                self.chat.set_status(self._status_text("就绪"))
            except Exception as exc:
                logger.exception("Skill 执行异常")
                self.chat.append_error(f"Skill 执行失败: {exc}")
                self.chat.set_status(self._status_text("就绪"))
            finally:
                self.chat.clear_tool_status()

        threading.Thread(target=worker, daemon=True, name="skill-run").start()

    def _handle_weather_intent(self, intent: InputIntent, text: str = "") -> None:
        range_label = "当天" if intent.weather_range == "1d" else "7天"
        self.chat.begin_assistant_progress("正在获取天气预报…")
        self.chat.set_tool_status(f"🌤 正在从中国天气网获取{range_label}预报…", accent="info")
        try:
            args: dict[str, str] = {
                "range_type": intent.weather_range,
                "query_text": text or "",
            }
            if intent.weather_city_code:
                args["city_code"] = intent.weather_city_code
            result = invoke_tool_in_process("get_weather_forecast", args)
            content_format = "html" if result.lstrip().startswith("<") else "markdown"
            self.chat.append_assistant_complete(result, content_format=content_format)
            self.chat.set_status(self._status_text("就绪"))
        except Exception as exc:
            logger.exception("获取天气预报失败")
            self.chat.append_error(f"获取天气预报失败: {exc}")
        finally:
            self.chat.clear_tool_status()

    def _handle_ocr_intent(
        self,
        text: str,
        attachments: list[dict[str, Any]],
        intent: InputIntent,
    ) -> None:
        if intent.kind == INTENT_SLASH_OCR and not any(
            att.get("type") == "image" for att in attachments
        ):
            self.chat.append_error("请先添加图片，或使用 /ocr 时粘贴/上传图片")
            self.chat.set_status(self._status_text("就绪"))
            return

        self.chat.begin_assistant_progress(ocr_progress_text())
        composed = compose_ocr_message(text, attachments)
        if not composed.get("ok"):
            err = composed.get("error") or "识别失败"
            self.chat.append_assistant_complete(f"识别失败：{err}")
            self.chat.set_status(self._status_text("就绪"))
            return
        for warn in composed.get("errors") or []:
            self.chat.append_system(warn)
        reply = format_ocr_reply(composed.get("ocr_results") or [])
        self.chat.append_assistant_complete(reply)
        self.chat.set_status(self._status_text("就绪"))

    def _start_link_summarize_turn(self, intent: InputIntent) -> None:
        self._compose_busy = False
        self._turn_user_query = intent.link_instruction
        self._running = True
        self.chat.set_running(True)
        self.chat.set_status(self._status_text("获取链接…"))
        threading.Thread(
            target=self._run_link_summarize_turn,
            args=(intent.link_instruction, list(intent.urls)),
            daemon=True,
            name="link-summarize",
        ).start()

    def _run_link_summarize_turn(self, instruction: str, urls: list[str]) -> None:
        try:
            if self._compose_cancel.is_set() or not self._llm:
                if not self._llm:
                    self.chat.append_error("Agent 未就绪，请检查 LLM 配置与 API Key。")
                return

            self.chat.begin_assistant()

            def on_token(token: str) -> None:
                if not self._compose_cancel.is_set():
                    self.chat.append_token(token)

            def on_status(status_text: str, accent: str | None) -> None:
                self.chat.set_tool_status(status_text, accent=accent)

            response, _fetches = run_link_summarize_turn(
                self._llm,
                instruction,
                urls,
                on_token=on_token,
                on_status=on_status,
                cancel_check=self._compose_cancel.is_set,
            )

            if self._compose_cancel.is_set():
                return

            self.chat.end_assistant()
            self.chat.set_status(self._status_text("就绪"))
        except Exception as exc:
            logger.exception("链接总结失败")
            self.chat.append_error(f"链接处理失败: {exc}")
        finally:
            self._running = False
            self._compose_busy = False
            if not self._compose_cancel.is_set():
                self.chat.set_running(False)
            self.chat.clear_tool_status()
            self._reset_turn_state()

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

    def _start_agent_turn(self, text: str) -> None:
        self._compose_busy = False
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
        self.chat.append_assistant_complete(response)
        self.chat.set_status(self._status_text("搜索缓存命中"))

    def _start_search_turn(self, user_query: str) -> None:
        self._compose_busy = False
        self._turn_user_query = user_query
        self._turn_search_query = user_query
        self._turn_used_web_search = True
        self._turn_search_ok = False
        self._collecting_assistant = True
        self._running = True
        self.chat.set_running(True)
        self.chat.set_status(self._status_text("搜索中…"))
        threading.Thread(
            target=self._run_search_turn,
            args=(user_query,),
            daemon=True,
            name="search-turn",
        ).start()

    def _run_search_turn(self, user_query: str) -> None:
        try:
            if self._compose_cancel.is_set():
                return
            if not self._llm:
                self.chat.append_error("Agent 未就绪，请检查 LLM 配置与 API Key。")
                return

            self.chat.reset_assistant_for_tool()
            self.chat.begin_assistant()

            def on_token(token: str) -> None:
                if not self._compose_cancel.is_set():
                    self.chat.append_token(token)

            def on_status(status_text: str, accent: str | None) -> None:
                self.chat.set_tool_status(status_text, accent=accent)

            response, _raw, ok = run_web_search_turn(
                self._llm,
                user_query,
                on_token=on_token,
                on_search_status=on_status,
                cancel_check=self._compose_cancel.is_set,
            )

            if self._compose_cancel.is_set():
                return

            self._turn_search_ok = ok
            self.chat.end_assistant()
            self._search_cache.save_async(
                user_query,
                user_query,
                self.chat.assistant_stream_buffer or response,
                search_ok=ok,
                finished=True,
            )
            self.chat.set_status(self._status_text("就绪"))
        except Exception as exc:
            logger.exception("搜索流程失败")
            self.chat.append_error(f"搜索失败: {exc}")
        finally:
            self._running = False
            self._compose_busy = False
            if not self._compose_cancel.is_set():
                self.chat.set_running(False)
            self.chat.clear_tool_status()
            self._reset_turn_state()

    def stop_agent(self) -> None:
        if not self._is_busy():
            return

        self._compose_cancel.set()
        self._compose_busy = False

        if self._running and self.runner:
            self.runner.stop()

        self._running = False
        self.chat.append_user("用户强制中断", track_turn=False)
        self.chat.clear_turn_timer()
        self.chat.reset_assistant_for_tool()
        self.chat.clear_tool_status()
        self.chat.set_running(False)
        self.chat.set_status(self._status_text("就绪"))
        self._reset_turn_state()

    def new_session(self) -> dict[str, Any]:
        info = self._session_store.create_session("新会话")
        return self._activate_session(info.id, announce=True)

    def list_sessions_api(self) -> dict[str, Any]:
        return {
            "sessions": [
                {"id": s.id, "title": s.title, "active": s.id == self._session_id}
                for s in self._session_store.list_sessions()
            ]
        }

    def switch_session(self, session_id: str) -> dict[str, Any]:
        if session_id == self._session_id:
            return {"ok": True, **self.list_sessions_api()}
        if not self._session_store.get(session_id):
            return {"ok": False, "error": "会话不存在"}
        if self._is_busy():
            return {"ok": False, "error": "请等待当前任务完成"}
        return self._activate_session(session_id, announce=False)

    def delete_session(self, session_id: str) -> dict[str, Any]:
        sessions = self._session_store.list_sessions()
        if len(sessions) <= 1:
            return {"ok": False, "error": "至少保留一个会话"}
        if not self._session_store.delete(session_id):
            return {"ok": False, "error": "会话不存在"}
        if session_id == self._session_id:
            remaining = self._session_store.list_sessions()
            if remaining:
                return self._activate_session(remaining[0].id, announce=True)
        return {"ok": True, **self.list_sessions_api()}

    def rename_session(self, session_id: str, title: str) -> dict[str, Any]:
        if not self._session_store.rename(session_id, title):
            return {"ok": False, "error": "重命名失败"}
        return {"ok": True, **self.list_sessions_api()}

    def _activate_session(self, session_id: str, *, announce: bool) -> dict[str, Any]:
        info = self._session_store.get(session_id)
        if not info:
            return {"ok": False, "error": "会话不存在"}
        self._session_id = info.id
        self._thread_id = info.thread_id
        self.chat.clear()
        events = self._session_store.load_events(session_id)
        self._skip_persist_events = True
        try:
            for ev in events:
                window = self._get_window()
                if window:
                    payload = json.dumps(ev, ensure_ascii=False)
                    try:
                        window.evaluate_js(f"window.ChatApp.handleEvent({payload})")
                    except Exception:
                        pass
        finally:
            self._skip_persist_events = False
        if announce and not events:
            self.chat.append_system(f"新会话：{info.title}")
        self.chat.set_status(self._status_text("就绪"))
        return {
            "ok": True,
            "active_id": session_id,
            "events": events,
            **self.list_sessions_api(),
        }

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
        provider_name = self._current_provider_name

        def _worker() -> None:
            try:
                file_count, chunk_count = ingest_files_in_process(path_list, provider_name)
                log = f"完成：{file_count} 个文件，{chunk_count} 个文本块"
                self.chat.append_system(log)
            except Exception as exc:
                logger.exception("知识库导入失败")
                self.chat.append_system(f"导入失败: {exc}")

        threading.Thread(target=_worker, daemon=True, name="knowledge-import").start()
        return {"log": "已在后台开始导入，完成后会在会话中提示。", **self.knowledge_stats_text()}

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
        shutdown_process_pools(wait=False)
        if controller._graph_bundle:
            controller._graph_bundle.close()
