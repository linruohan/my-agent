"""AssistantController 核心初始化与共享状态。"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import webview
from loguru import logger

from src.agent.graph import AgentGraphBundle, build_agent_graph
from src.agent.runner import AgentRunner
from src.infra.config import ensure_data_dirs, load_app_config, load_merged_providers
from src.infra.user_settings import has_stored_api_key
from src.llm.factory import create_llm_with_fallback
from src.memory.rag import set_rag_provider
from src.memory.search_cache import SearchCache
from src.tools.note import NoteStore
from src.tools.task import TaskReminderService, TaskStore, migrate_legacy_todos_json
from src.ui.font_prefs import build_font_variables, get_font_prefs
from src.ui.session_store import SessionStore
from src.ui.theme_loader import build_css_variables, get_theme_prefs
from src.ui.web_bridge import WebChatBridge


class CoreMixin:
    """控制器核心：初始化、Agent、忙碌状态、聊天事件持久化。"""

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
        self._agent_reinit_lock = threading.Lock()
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

    def _status_text(self, suffix: str = "") -> str:
        p = self._current_provider
        base = f"模型: {self._current_provider_name} / {p.model}  |  会话: {self._thread_id[:8]}..."
        return f"{base}  |  {suffix}" if suffix else base

    def _ui_variables(self) -> dict[str, str]:
        vars_ = build_css_variables(self._theme_id, self._appearance)
        vars_.update(build_font_variables(self._font_id))
        return vars_

    def _init_agent(self) -> None:
        with self._agent_reinit_lock:
            self._init_agent_unlocked()

    def _init_agent_unlocked(self) -> None:
        try:
            if self._graph_bundle:
                self._graph_bundle.close()
            chain = self._provider_fallback_chain(self._current_provider_name, self._providers)
            self._llm, active_name = create_llm_with_fallback(self._providers, chain)
            if active_name != self._current_provider_name:
                logger.info("LLM 降级至 Provider: {}", active_name)
                self._current_provider_name = active_name
                self._current_provider = self._providers[active_name]
            set_rag_provider(self._current_provider)
            ckpt = Path(self.app_cfg["paths"]["checkpoints"]) / "agent.db"
            self._graph_bundle = build_agent_graph(self._llm, ckpt)
            self.runner = AgentRunner(graph=self._graph_bundle.graph)
            self.chat.set_status(self._status_text("就绪"))
        except Exception as exc:
            logger.exception("Agent 初始化失败")
            self.chat.append_error(f"Agent 初始化失败: {exc}")
            self.runner = AgentRunner(graph=None)

    def _schedule_agent_reinit(self) -> None:
        """后台重建 Agent，避免保存设置时阻塞 UI 或与运行中任务争用 checkpoint。"""

        def worker() -> None:
            for _ in range(100):
                if not self._running:
                    break
                time.sleep(0.1)
            with self._agent_reinit_lock:
                if self._running:
                    logger.warning("Agent 仍在运行，跳过设置触发的重建")
                    return
                self._init_agent_unlocked()

        threading.Thread(target=worker, daemon=True, name="agent-reinit").start()

    @staticmethod
    def _provider_fallback_chain(
        current: str,
        providers: dict[str, Any],
    ) -> list[str]:
        """当前 Provider 优先，其余有 API Key 的次之。"""
        chain = [current]
        for name, cfg in providers.items():
            if name in chain:
                continue
            if cfg.api_key_env and has_stored_api_key(cfg.api_key_env):
                chain.append(name)
            elif cfg.type == "ollama":
                chain.append(name)
        return chain

    def _is_busy(self) -> bool:
        return self._running or self._compose_busy

    def _maybe_save_search_cache(self, response: str) -> None:
        if self._turn_used_web_search and response.strip():
            self._search_cache.save_async(
                self._turn_user_query,
                self._turn_search_query or self._turn_user_query,
                response,
                search_ok=self._turn_search_ok,
                finished=True,
            )
        self._reset_turn_state()

    def _reset_turn_state(self) -> None:
        self._turn_user_query = ""
        self._turn_search_query = ""
        self._turn_used_web_search = False
        self._turn_search_ok = False
        self._collecting_assistant = False

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
