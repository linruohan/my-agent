from __future__ import annotations

import uuid
from pathlib import Path

import customtkinter as ctk
from loguru import logger

from src.agent.graph import AgentGraphBundle, build_agent_graph
from src.agent.runner import AgentRunner, StreamEvent
from src.infra.config import ensure_data_dirs, load_app_config, load_merged_providers
from src.llm.factory import create_llm
from src.llm.providers import ProviderConfig
from src.ui.chat_panel import ChatPanel
from src.ui.settings_dialog import SettingsDialog


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

        ctk.CTkButton(sidebar, text="⚙ 设置", command=self._open_settings).grid(
            row=3, column=0, padx=16, pady=16, sticky="ew"
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

        self.input_box = ctk.CTkTextbox(input_frame, height=80)
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
            llm = create_llm(self._current_provider)
            ckpt = Path(self.app_cfg["paths"]["checkpoints"]) / "agent.db"
            self._graph_bundle = build_agent_graph(llm, ckpt)
            self.runner = AgentRunner(graph=self._graph_bundle.graph)
            self.status_bar.configure(text=self._status_text() + "  |  就绪")
        except Exception as exc:
            logger.exception("Agent 初始化失败")
            self.chat.append_error(f"Agent 初始化失败: {exc}")
            self.runner = AgentRunner(graph=None)

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
        text = self.input_box.get("1.0", "end").strip()
        if not text:
            return
        if not self.runner.graph:
            self.chat.append_error("Agent 未就绪，请检查 LLM 配置与 API Key。")
            return

        self.input_box.delete("1.0", "end")
        self.chat.append_user(text)
        self._running = True
        self.send_btn.configure(state="disabled")
        self.runner.run_async(text, self._thread_id)

    def _stop(self) -> None:
        if self._running:
            self.runner.stop()
            self.chat.append_system("已请求停止。")

    def _poll_agent_events(self) -> None:
        if self.runner and self.runner.graph:

            def handle(event: StreamEvent) -> None:
                if event.kind == "token":
                    self.chat.append_token(event.payload)
                elif event.kind == "tool_call":
                    p = event.payload
                    self.chat.append_tool_call(p["name"], p.get("args", {}))
                elif event.kind == "tool_result":
                    p = event.payload
                    self.chat.append_tool_result(p["name"], p["content"])
                elif event.kind == "done":
                    self.chat.end_assistant()
                    self._running = False
                    self.send_btn.configure(state="normal")
                elif event.kind == "error":
                    self.chat.append_error(event.payload)
                    self._running = False
                    self.send_btn.configure(state="normal")
                elif event.kind == "stopped":
                    self._running = False
                    self.send_btn.configure(state="normal")

            still_running = self.runner.poll_events(handle)
            if not still_running and self._running:
                self._running = False
                self.send_btn.configure(state="normal")

        self.after(50, self._poll_agent_events)


def run_app() -> None:
    app = AssistantApp()
    app.mainloop()
