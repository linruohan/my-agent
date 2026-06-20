"""输入附件处理与用户消息拼装。"""

from __future__ import annotations

import base64
import mimetypes
import re
import uuid
from pathlib import Path
from typing import Any

from src.infra.paths import DATA_DIR
from src.ui.link_fetch_worker import summarize_url_in_process
from src.ui.message_utils import normalize_user_message
from src.ui.ocr_worker import ocr_image_path_in_process

TEMP_INPUT_DIR = DATA_DIR / "temp" / "input"
_URL_RE = re.compile(r"https?://[^\s\])<>\"']+")
_OCR_ONLY_TEXT_RE = re.compile(
    r"^(?:识别(?:文本|文字|图片)?|文字识别|图片识别|提取文字|ocr)(?:[\s，。!！?？、]*)?$",
    re.IGNORECASE,
)


def ensure_temp_dir() -> Path:
    TEMP_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    return TEMP_INPUT_DIR


def image_to_data_url(path: str | Path, *, max_bytes: int = 8_000_000) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": f"图片不存在: {p}"}
    size = p.stat().st_size
    if size > max_bytes:
        return {"ok": False, "error": f"图片过大 ({size // 1024}KB)，暂不支持预览"}
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    encoded = base64.b64encode(p.read_bytes()).decode("ascii")
    return {"ok": True, "data_url": f"data:{mime};base64,{encoded}", "name": p.name}


def build_image_previews(attachments: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    previews: list[dict[str, str]] = []
    for att in attachments or []:
        if att.get("type") != "image":
            continue
        path = str(att.get("path", "")).strip()
        if not path:
            continue
        result = image_to_data_url(path)
        if not result.get("ok"):
            continue
        previews.append(
            {
                "path": path,
                "name": str(att.get("name") or Path(path).name),
                "data_url": str(result["data_url"]),
            }
        )
    return previews


def save_temp_image_b64(data_b64: str, *, ext: str = "png") -> dict[str, Any]:
    try:
        raw = base64.b64decode(data_b64.split(",", 1)[-1])
    except Exception as exc:
        return {"ok": False, "error": f"图片数据无效: {exc}"}
    ensure_temp_dir()
    path = TEMP_INPUT_DIR / f"paste_{uuid.uuid4().hex[:12]}.{ext.lstrip('.')}"
    path.write_bytes(raw)
    return {"ok": True, "path": str(path.resolve())}


def process_image_ocr(att: dict[str, Any]) -> dict[str, Any]:
    """仅 OCR 图片附件。"""
    path = str(att.get("path", "")).strip()
    if not path:
        return {"ok": False, "error": "图片路径为空"}
    ocr = ocr_image_path_in_process(path)
    if not ocr.get("ok"):
        return ocr
    name = att.get("name") or Path(path).name
    block = f"### 图片 OCR ({name})\n{ocr.get('text', '')}"
    return {"ok": True, "block": block, "kind": "image", "ocr": ocr.get("text", "")}


def process_attachment(att: dict[str, Any], *, ocr_images: bool = True) -> dict[str, Any]:
    """处理单个附件，返回 {ok, block} 供拼装。"""
    kind = att.get("type")
    if kind == "file":
        path = str(att.get("path", "")).strip()
        if not path:
            return {"ok": False, "error": "文件路径为空"}
        name = att.get("name") or Path(path).name
        block = f"### 附件文件\n- 名称: {name}\n- 路径: `{path}`"
        return {"ok": True, "block": block, "kind": kind}

    if kind == "image":
        if not ocr_images:
            path = str(att.get("path", "")).strip()
            name = att.get("name") or Path(path).name or "图片"
            block = f"### 图片\n- 名称: {name}\n- 路径: `{path}`"
            return {"ok": True, "block": block, "kind": kind}
        return process_image_ocr(att)

    if kind == "link":
        url = str(att.get("url", "")).strip()
        if not url:
            return {"ok": False, "error": "链接为空"}
        fetched = summarize_url_in_process(url)
        if not fetched.get("ok"):
            return fetched
        block = f"### 链接摘要\n- URL: {url}\n\n{fetched.get('summary', '')}"
        return {"ok": True, "block": block, "kind": kind, "summary": fetched.get("summary", "")}

    return {"ok": False, "error": f"未知附件类型: {kind}"}


def extract_inline_urls(text: str) -> list[str]:
    return list(dict.fromkeys(_URL_RE.findall(text or "")))


def has_sendable_content(text: str, attachments: list[dict[str, Any]] | None = None) -> bool:
    attachments = attachments or []
    return bool(normalize_user_message(text or "").strip() or attachments)


def is_ocr_only_request(text: str, attachments: list[dict[str, Any]] | None = None) -> bool:
    """仅图片识别：无文字或文字仅为识别意图，且不包含文件/链接等非图片附件。"""
    attachments = attachments or []
    if not attachments:
        return False
    if any(att.get("type") != "image" for att in attachments):
        return False
    body = normalize_user_message(text or "").strip()
    if not body:
        return True
    return bool(_OCR_ONLY_TEXT_RE.fullmatch(body))


def format_ocr_reply(ocr_results: list[dict[str, str]]) -> str:
    if not ocr_results:
        return "(未识别到文字)"
    parts: list[str] = []
    for item in ocr_results:
        name = item.get("name") or "图片"
        text = (item.get("text") or "").strip() or "(未识别到文字)"
        if len(ocr_results) > 1:
            parts.append(f"**{name}**\n\n{text}")
        else:
            parts.append(text)
    return "\n\n".join(parts)


def compose_ocr_message(text: str, attachments: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """仅对图片执行 OCR。"""
    attachments = attachments or []
    image_atts = [att for att in attachments if att.get("type") == "image"]
    if not image_atts:
        return {"ok": False, "error": "请先添加图片", "errors": ["请先添加图片"]}

    errors: list[str] = []
    ocr_results: list[dict[str, str]] = []
    for att in image_atts:
        result = process_image_ocr(att)
        if result.get("ok"):
            path = str(att.get("path", "")).strip()
            ocr_results.append(
                {
                    "name": str(att.get("name") or Path(path).name or "图片"),
                    "text": str(result.get("ocr") or ""),
                }
            )
        else:
            errors.append(str(result.get("error", "识别失败")))

    if not ocr_results:
        return {"ok": False, "error": errors[0] if errors else "识别失败", "errors": errors}

    return {
        "ok": True,
        "message": "",
        "user_text": normalize_user_message(text or ""),
        "ocr_results": ocr_results,
        "errors": errors,
        "ocr_only": True,
    }


def compose_user_message(
    text: str,
    attachments: list[dict[str, Any]] | None = None,
    *,
    ocr_images: bool = True,
    fetch_inline_urls: bool = True,
) -> dict[str, Any]:
    """将文本与附件（含 OCR / 链接摘要）合并为发送给 Agent 的消息。"""
    attachments = attachments or []
    blocks: list[str] = []
    errors: list[str] = []
    ocr_results: list[dict[str, str]] = []

    body = normalize_user_message(text or "")
    if body:
        blocks.append(body)

    for att in attachments:
        result = process_attachment(att, ocr_images=ocr_images)
        if result.get("ok"):
            blocks.append(str(result["block"]))
            if result.get("kind") == "image" and ocr_images:
                path = str(att.get("path", "")).strip()
                ocr_results.append(
                    {
                        "name": str(att.get("name") or Path(path).name or "图片"),
                        "text": str(result.get("ocr") or ""),
                    }
                )
        else:
            errors.append(str(result.get("error", "附件处理失败")))

    if fetch_inline_urls:
        for url in extract_inline_urls(body):
            if any(att.get("url") == url for att in attachments if att.get("type") == "link"):
                continue
            fetched = summarize_url_in_process(url)
            if fetched.get("ok"):
                blocks.append(f"### 链接摘要\n- URL: {url}\n\n{fetched.get('summary', '')}")
            else:
                errors.append(f"链接 {url}: {fetched.get('error', '抓取失败')}")

    if not blocks:
        return {"ok": False, "error": "请输入内容或添加附件", "errors": errors}

    message = "\n\n".join(blocks)
    return {
        "ok": True,
        "message": message,
        "user_text": body,
        "ocr_results": ocr_results,
        "errors": errors,
        "ocr_only": is_ocr_only_request(text, attachments),
    }
