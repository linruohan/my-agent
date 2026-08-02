"""Playwright 抓取网页并生成简要摘要。"""

from __future__ import annotations

import atexit
import re
import threading
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from loguru import logger

from src.infra.config import load_search_config
from src.infra.http_client import shared_http_client

_pw_lock = threading.Lock()
_pw_runtime: tuple[Any, Any] | None = None  # (playwright, browser)


def _default_headers() -> dict[str, str]:
    cfg = load_search_config().get("search", {})
    ua = cfg.get(
        "user_agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    )
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def _meaningful_length(text: str) -> int:
    """去掉空白后的有效字符数，用于判断页面是否过空。"""
    return len(re.sub(r"\s+", "", text or ""))


def _is_sparse_content(text: str, *, min_chars: int = 280) -> bool:
    return _meaningful_length(text) < min_chars


def _extract_readable_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        tag.decompose()
    title = (soup.title.string or "").strip() if soup.title else ""
    body = soup.body.get_text("\n", strip=True) if soup.body else soup.get_text("\n", strip=True)
    body = _normalize_whitespace(body)
    if title:
        return f"标题: {title}\n\n{body}"
    return body


def _summarize_text(text: str, *, max_chars: int = 8000) -> str:
    text = _normalize_whitespace(text)
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.65)]
    tail = text[-int(max_chars * 0.25) :]
    return f"{head}\n\n…\n\n{tail}"


def _validate_url(url: str) -> str:
    u = url.strip()
    parsed = urlparse(u)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("无效的 URL")
    return u


def _result_payload(
    url: str,
    text: str,
    *,
    engine: str,
    note: str = "",
) -> dict[str, Any]:
    summary = _summarize_text(text)
    sparse = _is_sparse_content(summary)
    payload: dict[str, Any] = {
        "ok": True,
        "url": url,
        "summary": summary,
        "engine": engine,
        "sparse": sparse,
        "char_count": len(summary),
    }
    if sparse:
        payload["warning"] = (
            "页面正文过少，热榜/列表等内容可能由 JavaScript 动态加载，"
            "静态抓取无法获取完整数据。"
        )
    if note:
        payload["note"] = note
    return payload


def _fetch_with_httpx(url: str) -> dict[str, Any]:
    resp = shared_http_client().get(
        url, headers=_default_headers(), timeout=25.0
    )
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "")
    if "html" not in content_type.lower() and "<html" not in resp.text[:500].lower():
        return {"ok": False, "error": "链接不是可读的 HTML 页面"}
    text = _extract_readable_text(resp.text)
    return _result_payload(url, text, engine="httpx")


def _get_shared_browser() -> Any:
    """进程内复用 Chromium，避免每次 summarize_url 冷启动。"""
    global _pw_runtime
    with _pw_lock:
        if _pw_runtime is not None:
            return _pw_runtime[1]
        from playwright.sync_api import sync_playwright  # type: ignore[import-untyped]

        from src.tools.browser.config import load_browser_config

        cfg = load_browser_config()
        pw = sync_playwright().start()
        launch_kwargs: dict[str, Any] = {"headless": True}
        args = cfg.get("chromium_args") or []
        if args:
            launch_kwargs["args"] = list(args)
        browser = pw.chromium.launch(**launch_kwargs)
        _pw_runtime = (pw, browser)
        return browser


def _shutdown_shared_browser() -> None:
    global _pw_runtime
    with _pw_lock:
        if _pw_runtime is None:
            return
        pw, browser = _pw_runtime
        _pw_runtime = None
        try:
            browser.close()
        except Exception:
            pass
        try:
            pw.stop()
        except Exception:
            pass


atexit.register(_shutdown_shared_browser)


def _fetch_with_playwright(url: str) -> dict[str, Any]:
    from src.tools.browser.config import load_browser_config
    from src.tools.browser.media import install_media_blocker

    browser = _get_shared_browser()
    cfg = load_browser_config()
    context = browser.new_context(user_agent=_default_headers()["User-Agent"])
    page = context.new_page()
    try:
        page.set_extra_http_headers(
            {"Accept-Language": _default_headers()["Accept-Language"]}
        )
        if cfg.get("block_media", True):
            install_media_blocker(page)
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1500)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            logger.debug("等待 networkidle 超时，继续抓取", exc_info=True)
        try:
            page.evaluate("window.scrollTo(0, Math.min(document.body.scrollHeight, 2400))")
            page.wait_for_timeout(800)
        except Exception:
            logger.debug("页面滚动失败，继续抓取", exc_info=True)
        title = page.title()
        body = page.inner_text("body")
        text = _normalize_whitespace(f"标题: {title}\n\n{body}" if title else body)
        return _result_payload(url, text, engine="playwright")
    finally:
        try:
            context.close()
        except Exception:
            pass


def summarize_url(url: str) -> dict[str, Any]:
    """抓取 URL 内容；优先 Playwright，失败回退 httpx。"""
    try:
        url = _validate_url(url)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    playwright_error = ""
    try:
        return _fetch_with_playwright(url)
    except ImportError:
        logger.warning("[link-fetch] Playwright 未安装，回退 httpx（动态页面内容可能缺失）")
        playwright_error = "Playwright 未安装"
    except Exception as exc:
        playwright_error = str(exc)
        logger.warning("[link-fetch] Playwright 抓取失败: {}", exc)

    try:
        result = _fetch_with_httpx(url)
        if result.get("ok") and playwright_error:
            note = (
                "Playwright 不可用或未安装浏览器，已回退 httpx。"
                "若页面为 SPA/热榜等动态内容，请运行: pip install playwright && playwright install chromium"
            )
            result["note"] = note
            if result.get("sparse"):
                result["warning"] = (
                    str(result.get("warning", ""))
                    + " "
                    + note
                ).strip()
        return result
    except Exception as httpx_exc:
        err = f"Playwright: {playwright_error}; httpx: {httpx_exc}" if playwright_error else str(httpx_exc)
        return {"ok": False, "error": err}
