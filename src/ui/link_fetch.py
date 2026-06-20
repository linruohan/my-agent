"""Playwright 抓取网页并生成简要摘要。"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


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


def _summarize_text(text: str, *, max_chars: int = 2400) -> str:
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


def _fetch_with_httpx(url: str) -> dict[str, Any]:
    headers = {"User-Agent": "my-agent/1.0"}
    with httpx.Client(follow_redirects=True, timeout=25.0, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type.lower() and "<html" not in resp.text[:500].lower():
            return {"ok": False, "error": "链接不是可读的 HTML 页面"}
        text = _extract_readable_text(resp.text)
        return {
            "ok": True,
            "url": url,
            "summary": _summarize_text(text),
            "engine": "httpx",
        }


def _fetch_with_playwright(url: str) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright  # type: ignore[import-untyped]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(800)
            title = page.title()
            body = page.inner_text("body")
            text = _normalize_whitespace(f"标题: {title}\n\n{body}" if title else body)
            return {
                "ok": True,
                "url": url,
                "summary": _summarize_text(text),
                "engine": "playwright",
            }
        finally:
            browser.close()


def summarize_url(url: str) -> dict[str, Any]:
    """抓取 URL 内容；优先 Playwright，失败回退 httpx。"""
    try:
        url = _validate_url(url)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        return _fetch_with_playwright(url)
    except ImportError:
        pass
    except Exception as exc:
        playwright_error = str(exc)
        try:
            result = _fetch_with_httpx(url)
            if result.get("ok"):
                result["note"] = f"Playwright 不可用，已回退 httpx（{playwright_error[:80]}）"
            return result
        except Exception as httpx_exc:
            return {"ok": False, "error": f"Playwright: {playwright_error}; httpx: {httpx_exc}"}

    try:
        return _fetch_with_httpx(url)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
