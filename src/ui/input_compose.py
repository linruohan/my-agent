"""输入附件处理与用户消息拼装。"""

from __future__ import annotations

import base64
import re
import uuid
from pathlib import Path
from typing import Any

from src.infra.paths import DATA_DIR
from src.ui.link_fetch import summarize_url
from src.ui.message_utils import normalize_user_message
from src.ui.ocr import ocr_image_path

TEMP_INPUT_DIR = DATA_DIR / "temp" / "input"
_URL_RE = re.compile(r"https?://[^\s\])<>\"']+")


def ensure_temp_dir() -> Path:
    TEMP_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    return TEMP_INPUT_DIR


def save_temp_image_b64(data_b64: str, *, ext: str = "png") -> dict[str, Any]:
    try:
        raw = base64.b64decode(data_b64.split(",", 1)[-1])
    except Exception as exc:
        return {"ok": False, "error": f"图片数据无效: {exc}"}
    ensure_temp_dir()
    path = TEMP_INPUT_DIR / f"paste_{uuid.uuid4().hex[:12]}.{ext.lstrip('.')}"
    path.write_bytes(raw)
    return {"ok": True, "path": str(path.resolve())}


def process_attachment(att: dict[str, Any]) -> dict[str, Any]:
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
        path = str(att.get("path", "")).strip()
        if not path:
            return {"ok": False, "error": "图片路径为空"}
        ocr = ocr_image_path(path)
        if not ocr.get("ok"):
            return ocr
        name = att.get("name") or Path(path).name
        block = f"### 图片 OCR ({name})\n{ocr.get('text', '')}"
        return {"ok": True, "block": block, "kind": kind, "ocr": ocr.get("text", "")}

    if kind == "link":
        url = str(att.get("url", "")).strip()
        if not url:
            return {"ok": False, "error": "链接为空"}
        fetched = summarize_url(url)
        if not fetched.get("ok"):
            return fetched
        block = f"### 链接摘要\n- URL: {url}\n\n{fetched.get('summary', '')}"
        return {"ok": True, "block": block, "kind": kind, "summary": fetched.get("summary", "")}

    return {"ok": False, "error": f"未知附件类型: {kind}"}


def extract_inline_urls(text: str) -> list[str]:
    return list(dict.fromkeys(_URL_RE.findall(text or "")))


def compose_user_message(text: str, attachments: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """将文本与附件（含 OCR / 链接摘要）合并为发送给 Agent 的消息。"""
    attachments = attachments or []
    blocks: list[str] = []
    errors: list[str] = []

    body = normalize_user_message(text or "")
    if body:
        blocks.append(body)

    for att in attachments:
        result = process_attachment(att)
        if result.get("ok"):
            blocks.append(str(result["block"]))
        else:
            errors.append(str(result.get("error", "附件处理失败")))

    # 文本中的裸链接也尝试抓取
    for url in extract_inline_urls(body):
        if any(att.get("url") == url for att in attachments if att.get("type") == "link"):
            continue
        fetched = summarize_url(url)
        if fetched.get("ok"):
            blocks.append(f"### 链接摘要\n- URL: {url}\n\n{fetched.get('summary', '')}")
        else:
            errors.append(f"链接 {url}: {fetched.get('error', '抓取失败')}")

    if not blocks:
        return {"ok": False, "error": "请输入内容或添加附件", "errors": errors}

    message = "\n\n".join(blocks)
    return {"ok": True, "message": message, "errors": errors}
