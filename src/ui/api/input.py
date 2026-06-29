"""输入附件与图片 API。"""

from __future__ import annotations

from typing import Any

from src.ui.api.base import ApiBase
from src.ui.input import save_temp_image_b64


class InputApiMixin(ApiBase):
    """图片/文件选择与粘贴。"""

    def pick_input_image(self) -> dict[str, Any]:
        return self._ctrl.pick_input_image()

    def pick_input_file(self) -> dict[str, Any]:
        return self._ctrl.pick_input_file()

    def save_pasted_image(self, data_b64: str) -> dict[str, Any]:
        return save_temp_image_b64(data_b64)

    def read_image_data_url(self, path: str) -> dict[str, Any]:
        from src.ui.input import image_to_data_url

        return image_to_data_url(path)
