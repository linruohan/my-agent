"""Playwright 浏览器操作实现。"""

from __future__ import annotations

import re
import time
from pathlib import Path

from src.tools.browser.config import load_browser_config
from src.tools.browser.session import BrowserSessionManager, screenshot_dir, validate_browser_url


def _normalize_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text or "")).strip()


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.75)]
    return f"{head}\n\n…（已截断，共 {len(text)} 字符）"


def browser_navigate_impl(url: str, session_id: str = "default", wait_until: str = "domcontentloaded") -> str:
    target = validate_browser_url(url)
    cfg = load_browser_config()
    wait = wait_until if wait_until in ("load", "domcontentloaded", "networkidle", "commit") else "domcontentloaded"

    def _go(page) -> str:
        page.goto(target, wait_until=wait, timeout=cfg["navigation_timeout_ms"])
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        title = page.title()
        current = page.url
        return f"已打开：{current}\n标题：{title or '（无）'}"

    return BrowserSessionManager.shared().run(session_id, _go)


def browser_click_impl(selector: str, session_id: str = "default") -> str:
    sel = (selector or "").strip()
    if not sel:
        return "请提供 CSS 选择器。"

    def _click(page) -> str:
        page.click(sel, timeout=load_browser_config()["timeout_ms"])
        return f"已点击 {sel}，当前页：{page.title()} ({page.url})"

    return BrowserSessionManager.shared().run(session_id, _click)


def browser_fill_impl(selector: str, text: str, session_id: str = "default", submit: bool = False) -> str:
    sel = (selector or "").strip()
    if not sel:
        return "请提供 CSS 选择器。"
    value = text if text is not None else ""

    def _fill(page) -> str:
        page.fill(sel, value, timeout=load_browser_config()["timeout_ms"])
        if submit:
            page.press(sel, "Enter")
        action = "已填写并提交" if submit else "已填写"
        return f"{action} {sel}，当前页：{page.title()} ({page.url})"

    return BrowserSessionManager.shared().run(session_id, _fill)


def browser_get_page_impl(session_id: str = "default", selector: str = "") -> str:
    cfg = load_browser_config()
    sel = (selector or "").strip()

    def _extract(page) -> str:
        title = page.title()
        url = page.url
        if sel:
            try:
                body = page.inner_text(sel)
            except Exception as exc:
                return f"无法读取选择器 {sel}：{exc}"
        else:
            body = page.inner_text("body")
        body = _truncate(_normalize_text(body), cfg["max_text_chars"])
        return f"URL: {url}\n标题: {title or '（无）'}\n\n{body or '（页面无文本）'}"

    return BrowserSessionManager.shared().run(session_id, _extract)


def browser_screenshot_impl(
    session_id: str = "default",
    save_path: str = "",
    full_page: bool = False,
) -> str:
    out_dir = screenshot_dir()

    def _shot(page) -> str:
        if save_path.strip():
            path = Path(save_path.strip())
            if not path.is_absolute():
                path = out_dir / path.name
        else:
            path = out_dir / f"shot-{int(time.time())}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(path), full_page=full_page)
        return f"截图已保存：{path}\n当前页：{page.title()} ({page.url})"

    return BrowserSessionManager.shared().run(session_id, _shot)


def browser_scroll_impl(session_id: str = "default", direction: str = "down", amount: int = 800) -> str:
    direction = (direction or "down").lower()
    px = max(100, min(int(amount or 800), 5000))
    delta = px if direction == "down" else -px

    def _scroll(page) -> str:
        page.evaluate(f"window.scrollBy(0, {delta})")
        page.wait_for_timeout(500)
        return f"已向{'下' if delta > 0 else '上'}滚动 {abs(delta)}px，当前：{page.url}"

    return BrowserSessionManager.shared().run(session_id, _scroll)


def browser_wait_selector_impl(selector: str, session_id: str = "default", timeout_ms: int = 10000) -> str:
    sel = (selector or "").strip()
    if not sel:
        return "请提供 CSS 选择器。"
    timeout = max(1000, min(int(timeout_ms or 10000), 60000))

    def _wait(page) -> str:
        page.wait_for_selector(sel, timeout=timeout)
        return f"元素已出现：{sel}，当前页：{page.title()} ({page.url})"

    return BrowserSessionManager.shared().run(session_id, _wait)


def browser_close_impl(session_id: str = "default") -> str:
    ok = BrowserSessionManager.shared().close(session_id)
    return f"已关闭浏览器会话「{session_id}」。" if ok else f"会话「{session_id}」不存在或已关闭。"


def browser_list_sessions_impl() -> str:
    sessions = BrowserSessionManager.shared().list_sessions()
    if not sessions:
        return "当前没有活跃的浏览器会话。"
    return "活跃浏览器会话：" + ", ".join(sessions)
