"""设置、知识库、模型 API。"""

from __future__ import annotations

from typing import Any

from src.ui.api.base import ApiBase


class SettingsApiMixin(ApiBase):
    """设置面板、知识库、Provider 模型。"""

    def get_settings_data(self) -> dict[str, Any]:
        return self._ctrl.build_settings_data()

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._ctrl.save_settings(payload)

    def save_provider(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._ctrl.save_provider(payload)

    def delete_provider(self, provider_id: str) -> dict[str, Any]:
        return self._ctrl.delete_provider(provider_id)

    def activate_provider(self, provider_id: str) -> dict[str, Any]:
        return self._ctrl.activate_provider_api(provider_id)

    def get_knowledge_stats(self) -> dict[str, str]:
        return self._ctrl.knowledge_stats_text()

    def import_knowledge(self, kind: str) -> dict[str, Any]:
        return self._ctrl.import_knowledge(kind)

    def list_provider_models(self) -> dict[str, Any]:
        return self._ctrl.list_provider_models_api()

    def set_model(self, model: str) -> dict[str, Any]:
        return self._ctrl.set_model(model)

    def save_chat_width(self, pct: int | float) -> dict[str, Any]:
        return self._ctrl.save_chat_width(pct)

    def pick_work_dir(self) -> dict[str, Any]:
        return self._ctrl.pick_work_dir()

    def get_slash_catalog(self) -> list[dict[str, Any]]:
        return self._ctrl.get_slash_catalog()

    def get_input_history(self) -> list[str]:
        return self._ctrl.get_input_history()

    def save_input_history(self, text: str) -> None:
        self._ctrl.save_input_history(text)
