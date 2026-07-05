"""初始状态与设置面板。"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import webview
from loguru import logger

from src.infra.config import load_llm_providers_config, save_api_key
from src.infra.user_settings import (
    activate_provider,
    create_user_provider,
    delete_provider_entry,
    has_stored_api_key,
    is_user_provider,
    provider_is_ready,
    load_user_settings,
    persist_provider_choice,
    provider_display_name,
    save_provider_entry,
    save_user_settings,
)
from src.llm.providers import parse_providers
from src.memory.rag import get_knowledge_stats
from src.memory.rag_worker import ingest_files_in_process
from src.ui.file_dialog import create_file_dialog_safe
from src.ui.input import append_history, list_history
from src.ui.prefs import font_prefs, layout_prefs, theme_prefs
from src.ui.skill import build_slash_catalog, get_skill_dirs
from src.ui.theme_loader import list_theme_catalog
from src.llm.models import list_provider_models_safe


class SettingsMixin:
    """设置、知识库、斜杠目录与输入历史。"""

    def get_slash_catalog(self) -> list[dict[str, Any]]:
        return build_slash_catalog()

    def get_input_history(self) -> list[str]:
        return list_history()

    def save_input_history(self, text: str) -> None:
        append_history(text)

    def build_initial_state(self) -> dict[str, Any]:
        app = self.app_cfg.get("app", {})
        settings = load_user_settings()
        owner_name = (settings.get("tasks") or {}).get("owner_name") or "林若寒"
        work_dir = layout_prefs.get_work_dir()
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
                "current_provider": self._current_provider_name,
                "current_model": self._current_provider.model,
                "provider_type": self._current_provider.type,
                "provider_base_url": self._current_provider.base_url or "",
            },
            "chat_width_pct": layout_prefs.get_chat_width_pct(),
            "workspace": {
                "owner_name": owner_name,
                "work_dir": str(work_dir) if work_dir else "",
                "work_dir_label": layout_prefs.format_work_dir_display(work_dir),
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

    def _base_provider_names(self) -> set[str]:
        _, base = parse_providers(load_llm_providers_config())
        return set(base.keys())

    def _provider_list_payload(self) -> list[dict[str, Any]]:
        settings = load_user_settings()
        base_names = self._base_provider_names()
        rows: list[dict[str, Any]] = []
        for name, p in self._providers.items():
            rows.append(
                {
                    "id": name,
                    "display_name": provider_display_name(name, settings),
                    "model": p.model,
                    "active": name == self._current_provider_name,
                    "deletable": is_user_provider(name, settings),
                    "type": p.type,
                    "base_url": p.base_url or "",
                    "temperature": p.temperature,
                    "has_api_key": provider_is_ready(p),
                    "is_builtin": name in base_names and not is_user_provider(name, settings),
                }
            )
        rows.sort(key=lambda r: (not r["active"], r["display_name"].lower()))
        return rows

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
            "font_catalog": font_prefs.list_catalog(),
            "font_id": self._font_id,
            "current_provider": self._current_provider_name,
            "provider_list": self._provider_list_payload(),
            "skill_dirs": "\n".join(str(x) for x in skill_dirs),
            "task_owner_name": (settings.get("tasks") or {}).get("owner_name") or "林若寒",
        }

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        theme_id = payload.get("theme_id") or "default"
        appearance = payload.get("appearance") or "dark"
        font_id = payload.get("font_id") or font_prefs.get_font_id()
        theme_prefs.persist(theme_id, appearance)
        font_prefs.persist(font_id)
        self._theme_id = theme_id
        self._appearance = appearance
        self._font_id = font_prefs.get_font_id()
        vars_ = self._ui_variables()

        skill_dirs_raw = (payload.get("skill_dirs") or "").strip()
        skill_dirs = [line.strip() for line in skill_dirs_raw.splitlines() if line.strip()]
        task_owner = (payload.get("task_owner_name") or "").strip() or "林若寒"
        settings = load_user_settings()
        ui = settings.setdefault("ui", {})
        ui["skill_dirs"] = skill_dirs
        tasks = settings.setdefault("tasks", {})
        tasks["owner_name"] = task_owner
        save_user_settings(settings)

        work_dir = layout_prefs.get_work_dir()
        return {
            "ok": True,
            "theme_variables": vars_,
            "status_text": self._status_text("设置已更新"),
            "workspace": {
                "owner_name": task_owner,
                "work_dir": str(work_dir) if work_dir else "",
                "work_dir_label": layout_prefs.format_work_dir_display(work_dir),
            },
            "composer_meta": {
                "current_provider": self._current_provider_name,
                "current_model": self._current_provider.model,
                "provider_type": self._current_provider.type,
                "provider_base_url": self._current_provider.base_url or "",
            },
        }

    def save_provider(self, payload: dict[str, Any]) -> dict[str, Any]:
        provider_id = (payload.get("id") or "").strip()
        display_name = (payload.get("display_name") or "").strip()
        model = (payload.get("model") or "").strip()
        if not display_name:
            return {"ok": False, "error": "请填写显示名称"}
        if not model:
            return {"ok": False, "error": "请填写模型"}

        settings = load_user_settings()
        is_new = not provider_id
        if is_new:
            provider_id, p = create_user_provider(payload)
        else:
            if provider_id not in self._providers:
                return {"ok": False, "error": "提供商不存在"}
            p = self._providers[provider_id]
            p.model = model
            p.base_url = (payload.get("base_url") or p.base_url or "").strip()
            p.temperature = float(payload.get("temperature", p.temperature))
            if is_user_provider(provider_id, settings):
                ptype = (payload.get("type") or p.type).strip()
                if ptype:
                    p.type = ptype
            save_provider_entry(
                provider_id,
                p,
                display_name=display_name,
                is_user=is_user_provider(provider_id, settings),
            )

        api_key = (payload.get("api_key") or "").strip()
        if api_key and p.api_key_env:
            save_api_key(p.api_key_env, api_key)
        elif is_new and not has_stored_api_key(p.api_key_env):
            return {"ok": False, "error": "请填写 API Key"}

        self._reload_providers()
        self._schedule_agent_reinit()
        self.chat.set_status(self._status_text("提供商已保存"))
        return {
            "ok": True,
            "provider_list": self._provider_list_payload(),
            "composer_meta": {
                "current_provider": self._current_provider_name,
                "current_model": self._current_provider.model,
                "provider_type": self._current_provider.type,
                "provider_base_url": self._current_provider.base_url or "",
            },
            "status_text": self._status_text("提供商已保存"),
        }

    def delete_provider(self, provider_id: str) -> dict[str, Any]:
        name = (provider_id or "").strip()
        if not name or name not in self._providers:
            return {"ok": False, "error": "提供商不存在"}

        settings = load_user_settings()
        is_user = is_user_provider(name, settings)
        if not is_user and name in self._base_provider_names():
            delete_provider_entry(name, is_user=False)
        elif is_user:
            delete_provider_entry(name, is_user=True)
        else:
            return {"ok": False, "error": "无法删除该提供商"}

        self._reload_providers()
        self._schedule_agent_reinit()
        self.chat.set_status(self._status_text("提供商已删除"))
        return {
            "ok": True,
            "provider_list": self._provider_list_payload(),
            "composer_meta": {
                "current_provider": self._current_provider_name,
                "current_model": self._current_provider.model,
                "provider_type": self._current_provider.type,
                "provider_base_url": self._current_provider.base_url or "",
            },
            "status_text": self._status_text("提供商已删除"),
        }

    def activate_provider_api(self, provider_id: str) -> dict[str, Any]:
        name = (provider_id or "").strip()
        if not name or name not in self._providers:
            return {"ok": False, "error": "提供商不存在"}

        p = self._providers[name]
        if not provider_is_ready(p):
            return {"ok": False, "error": "请先配置 API Key"}

        activate_provider(name)
        settings = load_user_settings()
        persist_provider_choice(name, p, display_name=provider_display_name(name, settings))
        self._reload_providers()
        self._schedule_agent_reinit()
        status = self._status_text("已切换提供商")
        self.chat.set_status(status)
        return {
            "ok": True,
            "provider_list": self._provider_list_payload(),
            "composer_meta": {
                "current_provider": self._current_provider_name,
                "current_model": self._current_provider.model,
                "provider_type": self._current_provider.type,
                "provider_base_url": self._current_provider.base_url or "",
            },
            "status_text": status,
        }

    def _reload_providers(self) -> None:
        from src.infra.config import load_merged_providers

        self._current_provider_name, self._providers = load_merged_providers()
        self._current_provider = self._providers[self._current_provider_name]

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
                paths = create_file_dialog_safe(window, webview.FOLDER_DIALOG)
            else:
                paths = create_file_dialog_safe(
                    window,
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

    def list_provider_models_api(self) -> dict[str, Any]:
        p = self._current_provider
        models, error = list_provider_models_safe(p)
        return {
            "ok": error is None,
            "models": models,
            "current_model": p.model,
            "provider": self._current_provider_name,
            "error": error,
        }

    def set_model(self, model: str) -> dict[str, Any]:
        name = (model or "").strip()
        if not name:
            return {"ok": False, "error": "模型不能为空"}
        p = self._current_provider
        p.model = name
        settings = load_user_settings()
        persist_provider_choice(
            self._current_provider_name,
            p,
            display_name=provider_display_name(self._current_provider_name, settings),
        )
        self._providers[self._current_provider_name] = p
        self._current_provider = p
        self._schedule_agent_reinit()
        status = self._status_text("模型已更新")
        self.chat.set_status(status)
        return {
            "ok": True,
            "model": name,
            "status_text": status,
            "composer_meta": {
                "current_provider": self._current_provider_name,
                "current_model": self._current_provider.model,
                "provider_type": self._current_provider.type,
                "provider_base_url": self._current_provider.base_url or "",
            },
        }

    def save_chat_width(self, pct: int | float) -> dict[str, Any]:
        value = layout_prefs.persist_chat_width_pct(pct)
        return {"ok": True, "chat_width_pct": value}

    def pick_work_dir(self) -> dict[str, Any]:
        window = self._get_window()
        if window is None:
            return {"ok": False, "error": "窗口未就绪"}

        current = layout_prefs.get_work_dir()
        try:
            paths = create_file_dialog_safe(
                window,
                webview.FOLDER_DIALOG,
                directory=str(current) if current else "",
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        if not paths:
            return {"ok": False, "cancelled": True}

        path = Path(paths[0]).expanduser().resolve()
        if not path.is_dir():
            return {"ok": False, "error": "请选择有效文件夹"}

        try:
            layout_prefs.persist_work_dir(path)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

        label = layout_prefs.format_work_dir_display(path)
        status = self._status_text(f"工作目录: {path.name}")
        self.chat.set_status(status)
        return {
            "ok": True,
            "work_dir": str(path),
            "work_dir_label": label,
            "status_text": status,
        }
