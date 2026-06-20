"""链接抓取在独立子进程中执行（Playwright / httpx）。"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.infra.process_executor import run_in_process


def _summarize_url_worker(url: str) -> dict[str, Any]:
    from src.ui.link_fetch import summarize_url

    return summarize_url(url)


def summarize_url_in_process(url: str, *, timeout: float = 90) -> dict[str, Any]:
    try:
        return run_in_process(_summarize_url_worker, url, pool="ui", timeout=timeout)
    except Exception as exc:
        logger.warning("[link-fetch] 子进程抓取失败: {}", exc)
        return {"ok": False, "error": str(exc)}
