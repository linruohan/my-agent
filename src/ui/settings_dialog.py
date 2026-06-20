from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from src.infra.config import save_api_key
from src.infra.user_settings import has_stored_api_key, persist_provider_choice
from src.llm.providers import ProviderConfig, parse_providers


class SettingsDialog(ctk.CTkToplevel):
    """LLM 与 Agent 设置面板。"""

    def __init__(
        self,
        master,
        current_provider: str,
        providers: dict[str, ProviderConfig],
        on_save: Callable[[str, ProviderConfig], None],
    ):
        super().__init__(master)
        self.title("设置")
        self.geometry("520x500")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self._on_save = on_save
        self._providers = providers

        ctk.CTkLabel(self, text="LLM 提供商", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=20, pady=(20, 4)
        )

        names = list(self._providers.keys())
        self.provider_var = ctk.StringVar(value=current_provider)
        self.provider_menu = ctk.CTkOptionMenu(
            self, values=names, variable=self.provider_var, command=self._on_provider_change
        )
        self.provider_menu.pack(fill="x", padx=20, pady=4)

        self.model_label = ctk.CTkLabel(self, text="模型名称")
        self.model_label.pack(anchor="w", padx=20, pady=(12, 4))
        self.model_entry = ctk.CTkEntry(self)
        self.model_entry.pack(fill="x", padx=20, pady=4)

        self.base_url_label = ctk.CTkLabel(self, text="API Base URL")
        self.base_url_label.pack(anchor="w", padx=20, pady=(12, 4))
        self.base_url_entry = ctk.CTkEntry(self)
        self.base_url_entry.pack(fill="x", padx=20, pady=4)

        self.api_key_label = ctk.CTkLabel(self, text="API Key")
        self.api_key_label.pack(anchor="w", padx=20, pady=(12, 4))
        self.api_key_entry = ctk.CTkEntry(self, show="*", placeholder_text="输入新 Key 或留空保留已有")
        self.api_key_entry.pack(fill="x", padx=20, pady=4)

        self.api_key_status = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=12), text_color="gray60"
        )
        self.api_key_status.pack(anchor="w", padx=20, pady=(2, 0))

        self.temp_label = ctk.CTkLabel(self, text="Temperature")
        self.temp_label.pack(anchor="w", padx=20, pady=(12, 4))
        self.temp_slider = ctk.CTkSlider(self, from_=0, to=1, number_of_steps=20)
        self.temp_slider.set(0.7)
        self.temp_slider.pack(fill="x", padx=20, pady=4)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=24)
        ctk.CTkButton(btn_frame, text="取消", width=100, fg_color="gray40", command=self.destroy).pack(
            side="right", padx=(8, 0)
        )
        ctk.CTkButton(btn_frame, text="保存", width=100, command=self._save).pack(side="right")

        self._on_provider_change(self.provider_var.get())

    def _on_provider_change(self, name: str) -> None:
        p = self._providers.get(name)
        if not p:
            return
        self.model_entry.delete(0, "end")
        self.model_entry.insert(0, p.model)
        self.base_url_entry.delete(0, "end")
        if p.base_url:
            self.base_url_entry.insert(0, p.base_url)
        self.temp_slider.set(p.temperature)

        self.api_key_entry.delete(0, "end")
        if has_stored_api_key(p.api_key_env):
            self.api_key_status.configure(
                text="✓ 已配置 API Key（留空则保留，输入新值则覆盖）",
                text_color="#4ade80",
            )
        else:
            self.api_key_status.configure(
                text="尚未配置 API Key",
                text_color="#f87171",
            )

    def _save(self) -> None:
        name = self.provider_var.get()
        p = self._providers[name]
        p.model = self.model_entry.get().strip() or p.model
        p.base_url = self.base_url_entry.get().strip() or p.base_url
        p.temperature = float(self.temp_slider.get())

        api_key = self.api_key_entry.get().strip()
        if api_key and p.api_key_env:
            save_api_key(p.api_key_env, api_key)
        elif not has_stored_api_key(p.api_key_env):
            self.api_key_status.configure(text="请填写 API Key", text_color="#f87171")
            return

        persist_provider_choice(name, p)
        self._providers[name] = p
        self._on_save(name, p)
        self.grab_release()
        self.destroy()
