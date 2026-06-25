"""LangChain 工具：Playwright 浏览器自动化。"""

from __future__ import annotations

from langchain_core.tools import tool

from src.tools.browser.core import (
    browser_click_impl,
    browser_close_impl,
    browser_fill_impl,
    browser_get_page_impl,
    browser_list_sessions_impl,
    browser_navigate_impl,
    browser_screenshot_impl,
    browser_scroll_impl,
    browser_wait_selector_impl,
)


@tool
def browser_navigate(url: str, session_id: str = "default", wait_until: str = "domcontentloaded") -> str:
    """用 Playwright 打开网页（支持 JavaScript 渲染）。同 session_id 可连续多步操作。

    Args:
        url: http/https 链接
        session_id: 浏览器会话 ID，默认 default
        wait_until: load / domcontentloaded / networkidle
    """
    try:
        return browser_navigate_impl(url, session_id=session_id, wait_until=wait_until)
    except Exception as exc:
        return f"导航失败：{exc}"


@tool
def browser_get_page(session_id: str = "default", selector: str = "") -> str:
    """获取当前页面标题、URL 与正文文本（动态页面友好）。

    Args:
        session_id: 浏览器会话 ID
        selector: 可选 CSS 选择器，仅提取该区域文本
    """
    try:
        return browser_get_page_impl(session_id=session_id, selector=selector)
    except Exception as exc:
        return f"读取页面失败：{exc}"


@tool
def browser_click(selector: str, session_id: str = "default") -> str:
    """点击页面元素。

    Args:
        selector: CSS 选择器，如 button.submit、#login
        session_id: 浏览器会话 ID
    """
    try:
        return browser_click_impl(selector, session_id=session_id)
    except Exception as exc:
        return f"点击失败：{exc}"


@tool
def browser_fill(selector: str, text: str, session_id: str = "default", submit: bool = False) -> str:
    """在输入框填写文本；可选提交（Enter）。敏感操作，执行前需用户确认。

    Args:
        selector: CSS 选择器
        text: 要填写的内容
        session_id: 浏览器会话 ID
        submit: 填写后是否按 Enter 提交
    """
    try:
        return browser_fill_impl(selector, text, session_id=session_id, submit=submit)
    except Exception as exc:
        return f"填写失败：{exc}"


@tool
def browser_wait_selector(selector: str, session_id: str = "default", timeout_ms: int = 10000) -> str:
    """等待元素出现在页面上。

    Args:
        selector: CSS 选择器
        session_id: 浏览器会话 ID
        timeout_ms: 超时毫秒数
    """
    try:
        return browser_wait_selector_impl(selector, session_id=session_id, timeout_ms=timeout_ms)
    except Exception as exc:
        return f"等待失败：{exc}"


@tool
def browser_scroll(session_id: str = "default", direction: str = "down", amount: int = 800) -> str:
    """滚动页面。

    Args:
        session_id: 浏览器会话 ID
        direction: down 或 up
        amount: 滚动像素
    """
    try:
        return browser_scroll_impl(session_id=session_id, direction=direction, amount=amount)
    except Exception as exc:
        return f"滚动失败：{exc}"


@tool
def browser_screenshot(session_id: str = "default", save_path: str = "", full_page: bool = False) -> str:
    """对当前页面截图，保存到 data/workspace/browser_screenshots/。

    Args:
        session_id: 浏览器会话 ID
        save_path: 可选文件名或路径
        full_page: 是否全页截图
    """
    try:
        return browser_screenshot_impl(session_id=session_id, save_path=save_path, full_page=full_page)
    except Exception as exc:
        return f"截图失败：{exc}"


@tool
def browser_close(session_id: str = "default") -> str:
    """关闭浏览器会话并释放资源。

    Args:
        session_id: 要关闭的会话 ID
    """
    return browser_close_impl(session_id=session_id)


@tool
def browser_list_sessions() -> str:
    """列出当前活跃的浏览器会话 ID。"""
    return browser_list_sessions_impl()


BROWSER_TOOLS = [
    browser_navigate,
    browser_get_page,
    browser_click,
    browser_fill,
    browser_wait_selector,
    browser_scroll,
    browser_screenshot,
    browser_close,
    browser_list_sessions,
]
