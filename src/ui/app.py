from __future__ import annotations

import queue
import uuid
from pathlib import Path

import customtkinter as ctk
from loguru import logger

from src.agent.graph import AgentGraphBundle, build_agent_graph
from src.agent.runner import AgentRunner, StreamEvent
from src.infra.config import ensure_data_dirs, load_app_config, load_merged_providers
from src.llm.factory import create_llm
from src.llm.providers import ProviderConfig
from src.memory.rag import set_rag_provider
from src.memory.search_cache import SearchCache
from src.ui.chat_panel import ChatPanel, normalize_user_message
from src.ui.confirm_dialog import ConfirmDialog
from src.ui.knowledge_dialog import KnowledgeDialog
from src.ui.settings_dialog import SettingsDialog
from src.ui.theme import CORNER_RADIUS


class AssistantApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ensure_data_dirs()
        self.app_cfg = load_app_config()
        self._current_provider_name, self._providers = load_merged_providers()
        self._current_provider = self._providers[self._current_provider_name]

        title = self.app_cfg.get("app", {}).get("title", "个人助理 Agent")
        self.title(title)
        w = self.app_cfg.get("app", {}).get("window_width", 1100)
        h = self.app_cfg.get("app", {}).get("window_height", 720)
        self.geometry(f"{w}x{h}")
        ctk.set_appearance_mode(self.app_cfg.get("app", {}).get("theme", "dark"))
        self._thread_id = str(uuid.uuid4())
        self._running = False
        self._graph_bundle: AgentGraphBundle | None = None
        self._awaiting_approval = False
        self._search_cache = SearchCache()
        self._turn_user_query = ""
        self._turn_search_query = ""
        self._turn_used_web_search = False
        self._turn_search_ok = False
        self._turn_assistant_text = ""
        self._collecting_assistant = False

        self._build_layout()
        self._init_agent()
        self.after(50, self._poll_agent_events)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 侧边栏
        sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(sidebar, text="会话", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, padx=16, pady=(16, 8), sticky="w"
        )
        ctk.CTkButton(sidebar, text="＋ 新会话", command=self._new_session).grid(
            row=1, column=0, padx=16, pady=4, sticky="ew"
        )
        self.session_list = ctk.CTkTextbox(sidebar, height=200)
        self.session_list.grid(row=2, column=0, padx=16, pady=8, sticky="nsew")
        self.session_list.insert("1.0", "当前会话\n")
        self.session_list.configure(state="disabled")

        ctk.CTkButton(sidebar, text="📚 导入文档", command=self._open_knowledge).grid(
            row=3, column=0, padx=16, pady=4, sticky="ew"
        )
        ctk.CTkButton(sidebar, text="⚙ 设置", command=self._open_settings).grid(
            row=4, column=0, padx=16, pady=16, sticky="ew"
        )

        # 主区域
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self.chat = ChatPanel(main)
        self.chat.grid(row=0, column=0, sticky="nsew")

        input_frame = ctk.CTkFrame(main)
        input_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        input_frame.grid_columnconfigure(0, weight=1)

        self.input_box = ctk.CTkTextbox(input_frame, height=80, corner_radius=CORNER_RADIUS)
        self.input_box.grid(row=0, column=0, sticky="ew", padx=(8, 4), pady=8)
        self.input_box.bind("<Control-Return>", lambda e: self._send())

        btn_col = ctk.CTkFrame(input_frame, fg_color="transparent")
        btn_col.grid(row=0, column=1, padx=8, pady=8)
        self.send_btn = ctk.CTkButton(btn_col, text="发送", width=80, command=self._send)
        self.send_btn.pack(pady=4)
        self.stop_btn = ctk.CTkButton(
            btn_col, text="停止", width=80, fg_color="gray40", command=self._stop
        )
        self.stop_btn.pack(pady=4)

        self.status_bar = ctk.CTkLabel(
            main,
            text=self._status_text(),
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color="gray60",
        )
        self.status_bar.grid(row=2, column=0, sticky="ew", pady=(4, 0))

        self.chat.append_system("欢迎使用个人助理 Agent。配置 API Key 后即可开始对话（Ctrl+Enter 发送）。")

    def _status_text(self) -> str:
        p = self._current_provider
        return f"模型: {self._current_provider_name} / {p.model}  |  会话: {self._thread_id[:8]}..."

    def _init_agent(self) -> None:
        try:
            if self._graph_bundle:
                self._graph_bundle.close()
            set_rag_provider(self._current_provider)
            llm = create_llm(self._current_provider)
            ckpt = Path(self.app_cfg["paths"]["checkpoints"]) / "agent.db"
            self._graph_bundle = build_agent_graph(llm, ckpt)
            self.runner = AgentRunner(graph=self._graph_bundle.graph)
            self.status_bar.configure(text=self._status_text() + "  |  就绪")
        except Exception as exc:
            logger.exception("Agent 初始化失败")
            self.chat.append_error(f"Agent 初始化失败: {exc}")
            self.runner = AgentRunner(graph=None)

    def _open_knowledge(self) -> None:
        KnowledgeDialog(
            self,
            self._current_provider,
            on_done=lambda msg: self.chat.append_system(msg),
        )

    def _open_settings(self) -> None:
        SettingsDialog(
            self,
            self._current_provider_name,
            self._providers,
            self._apply_settings,
        )

    def _apply_settings(self, name: str, provider: ProviderConfig) -> None:
        self._current_provider_name = name
        self._current_provider = provider
        self._providers[name] = provider
        self._init_agent()
        self.chat.append_system(f"已切换 Provider: {name} / {provider.model}")

    def _new_session(self) -> None:
        self._thread_id = str(uuid.uuid4())
        self.chat.clear()
        self.chat.append_system(f"新会话已创建: {self._thread_id[:8]}...")
        self.status_bar.configure(text=self._status_text())

    def _send(self) -> None:
        if self._running:
            return
        text = normalize_user_message(self.input_box.get("1.0", "end"))
        if not text:
            return
        if not self.runner.graph:
            self.chat.append_error("Agent 未就绪，请检查 LLM 配置与 API Key。")
            return

        self.input_box.delete("1.0", "end")
        self.chat.append_user(text)

        cached = self._search_cache.lookup(text)
        if cached:
            self._deliver_cached_search(text, cached)
            return

        self._start_agent_turn(text)

    def _start_agent_turn(self, text: str) -> None:
        self._turn_user_query = text
        self._turn_search_query = ""
        self._turn_used_web_search = False
        self._turn_search_ok = False
        self._turn_assistant_text = ""
        self._collecting_assistant = False
        self._running = True
        self.send_btn.configure(state="disabled")
        self.status_bar.configure(text=self._status_text() + "  |  思考中…")
        self.runner.run_async(text, self._thread_id)

    def _deliver_cached_search(self, user_query: str, response: str) -> None:
        """命中搜索缓存，跳过 Agent / 工具 / LLM。"""
        self.chat.append_assistant_complete(response, from_cache=True)
        self.status_bar.configure(text=self._status_text() + "  |  搜索缓存命中")

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
        self._turn_assistant_text = ""
        self._collecting_assistant = False

    def _reset_turn_state(self) -> None:
        self._turn_user_query = ""
        self._turn_search_query = ""
        self._turn_used_web_search = False
        self._turn_search_ok = False
        self._turn_assistant_text = ""
        self._collecting_assistant = False

    def _stop(self) -> None:
        if self._running:
            self.runner.stop()
            self.chat.append_system("已请求停止。")

    def _handle_approval(self, payload: dict) -> None:
        if self._awaiting_approval:
            return
        self._awaiting_approval = True
        description = payload.get("description", "确认执行敏感操作？")

        def on_confirm() -> None:
            self._awaiting_approval = False
            self.runner.resume_after_approval(True)
            self.chat.append_system("已批准操作，正在执行...")

        def on_cancel() -> None:
            self._awaiting_approval = False
            self.runner.resume_after_approval(False)
            self.chat.append_system("已拒绝操作。")

        ConfirmDialog(
            self,
            title="敏感操作确认",
            description=description,
            on_confirm=on_confirm,
            on_cancel=on_cancel,
        )

    def _poll_agent_events(self) -> None:
        if self.runner and self.runner.graph:
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
                    self.send_btn.configure(state="normal")

        self.after(50, self._poll_agent_events)

    def _handle_agent_event(self, event: StreamEvent) -> bool:
        """处理单个 Agent 事件，返回是否仍在运行。"""
        if event.kind == "token":
            if self._collecting_assistant:
                self._turn_assistant_text += event.payload
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
                self._turn_assistant_text = ""
            self.chat.append_tool_result(p["name"], p["content"])
        elif event.kind == "approval_required":
            self._handle_approval(event.payload)
        elif event.kind == "done":
            response = self.chat.assistant_stream_buffer
            self.chat.end_assistant()
            self._maybe_save_search_cache(response)
            self._running = False
            self.send_btn.configure(state="normal")
            self.status_bar.configure(text=self._status_text() + "  |  就绪")
            return False
        elif event.kind == "error":
            self.chat.append_error(event.payload)
            self._reset_turn_state()
            self._running = False
            self.send_btn.configure(state="normal")
            return False
        elif event.kind == "stopped":
            self._reset_turn_state()
            self._running = False
            self.send_btn.configure(state="normal")
            return False
        return True


def run_app() -> None:
    app = AssistantApp()
    app.mainloop()
