"""暴露给 pywebview JS 的 API。"""

from __future__ import annotations

from typing import Any

from src.ui.clipboard import copy_to_clipboard as sys_copy_to_clipboard
from src.ui.controller import AssistantController
from src.ui.input import save_temp_image_b64
from src.ui.open_local import check_local_paths as sys_check_local_paths
from src.ui.open_local import open_local_path as sys_open_local_path


class AppApi:
    """pywebview js_api 桥接层。"""

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

    def list_provider_models(self) -> dict[str, Any]:
        return self._ctrl.list_provider_models_api()

    def set_model(self, model: str) -> dict[str, Any]:
        return self._ctrl.set_model(model)

    def save_chat_width(self, pct: int | float) -> dict[str, Any]:
        return self._ctrl.save_chat_width(pct)

    def copy_to_clipboard(self, text: str) -> bool:
        return sys_copy_to_clipboard(text)

    def open_local_path(self, path: str) -> dict[str, Any]:
        return sys_open_local_path(path)

    def check_local_paths(self, paths: list[str]) -> dict[str, bool]:
        return sys_check_local_paths(paths)
