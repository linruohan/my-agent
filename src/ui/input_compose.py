"""兼容层：请使用 src.ui.input.compose。"""
from src.ui.input.compose import (
    build_image_previews,
    compose_ocr_message,
    compose_user_message,
    ensure_temp_dir,
    extract_inline_urls,
    format_ocr_reply,
    has_sendable_content,
    image_to_data_url,
    is_ocr_only_request,
    process_attachment,
    process_image_ocr,
    save_temp_image_b64,
)

__all__ = [
    "build_image_previews",
    "compose_ocr_message",
    "compose_user_message",
    "ensure_temp_dir",
    "extract_inline_urls",
    "format_ocr_reply",
    "has_sendable_content",
    "image_to_data_url",
    "is_ocr_only_request",
    "process_attachment",
    "process_image_ocr",
    "save_temp_image_b64",
]
