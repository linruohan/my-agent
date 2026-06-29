"""初始状态与设置面板。"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import webview
from loguru import logger

from src.infra.config import save_api_key
from src.infra.user_settings import has_stored_api_key, is_voice_input_enabled, load_user_settings, persist_provider_choice, save_user_settings
from src.memory.rag import get_knowledge_stats
from src.memory.rag_worker import ingest_files_in_process
from src.ui.file_dialog import create_file_dialog_safe
from src.ui.font_prefs import get_font_prefs, list_font_catalog, lxgw_font_installed, persist_font_prefs
from src.ui.input import append_history, list_history
from src.ui.skill import build_slash_catalog, get_skill_dirs
from src.ui.speech import is_supported as voice_is_supported
from src.ui.theme_loader import list_theme_catalog, persist_theme_prefs
from src.ui.ui_prefs import get_chat_width_pct, get_work_dir, format_work_dir_display, persist_chat_width_pct, persist_work_dir
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
        voice_enabled = is_voice_input_enabled()
        settings = load_user_settings()
        owner_name = (settings.get("tasks") or {}).get("owner_name") or "林若寒"
        work_dir = get_work_dir()
        return {
            "title": app.get("title", "个人助理 Agent"),
            "theme_variables": self._ui_variables(),
            "theme_id": self._theme_id,
            "appearance": self._appearance,
            "font_id": self._font_id,
            "lxgw_font_installed": lxgw_font_installed(),
            "status_text": self._status_text("就绪"),
            "welcome": "欢迎使用个人助理 Agent。Enter 发送，Shift+Enter 换行。输入 / 查看命令。",
            "composer_meta": {
                "session_short": self._thread_id[:8],
                "voice_enabled": voice_enabled,
                "voice_supported": voice_is_supported() if voice_enabled else False,
                "current_provider": self._current_provider_name,
                "current_model": self._current_provider.model,
            },
            "chat_width_pct": get_chat_width_pct(),
            "workspace": {
                "owner_name": owner_name,
                "work_dir": str(work_dir) if work_dir else "",
                "work_dir_label": format_work_dir_display(work_dir),
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
            "task_owner_name": (settings.get("tasks") or {}).get("owner_name") or "林若寒",
            "voice_enabled": is_voice_input_enabled(),
            "voice_supported": voice_is_supported(),
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
        if font_id == "lxgw-wenkai-gb" and not lxgw_font_installed():
            self.chat.append_system(
                "霞鹜文楷字体未安装，已使用系统字体。请运行 scripts/install-web-fonts.ps1 后重选字体。"
            )
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
        task_owner = (payload.get("task_owner_name") or "").strip() or "林若寒"
        voice_enabled = bool(payload.get("voice_enabled"))
        settings = load_user_settings()
        ui = settings.setdefault("ui", {})
        ui["skill_dirs"] = skill_dirs
        ui["voice_enabled"] = voice_enabled
        tasks = settings.setdefault("tasks", {})
        tasks["owner_name"] = task_owner
        save_user_settings(settings)
        self._providers[name] = p
        self._schedule_agent_reinit()
        self.chat.set_status(self._status_text("设置已更新"))

        work_dir = get_work_dir()
        return {
            "ok": True,
            "theme_variables": vars_,
            "status_text": self._status_text("设置已更新"),
            "workspace": {
                "owner_name": task_owner,
                "work_dir": str(work_dir) if work_dir else "",
                "work_dir_label": format_work_dir_display(work_dir),
            },
            "composer_meta": {
                "voice_enabled": voice_enabled,
                "voice_supported": voice_is_supported() if voice_enabled else False,
                "current_provider": self._current_provider_name,
                "current_model": p.model,
            },
        }

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
        persist_provider_choice(self._current_provider_name, p)
        self._providers[self._current_provider_name] = p
        self._current_provider = p
        self._schedule_agent_reinit()
        status = self._status_text("模型已更新")
        self.chat.set_status(status)
        return {
            "ok": True,
            "model": name,
            "status_text": status,
        }

    def save_chat_width(self, pct: int | float) -> dict[str, Any]:
        value = persist_chat_width_pct(pct)
        return {"ok": True, "chat_width_pct": value}

    def pick_work_dir(self) -> dict[str, Any]:
        window = self._get_window()
        if window is None:
            return {"ok": False, "error": "窗口未就绪"}

        current = get_work_dir()
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
            persist_work_dir(path)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

        label = format_work_dir_display(path)
        status = self._status_text(f"工作目录: {path.name}")
        self.chat.set_status(status)
        return {
            "ok": True,
            "work_dir": str(path),
            "work_dir_label": label,
            "status_text": status,
        }
