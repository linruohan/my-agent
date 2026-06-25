"""Playwright 浏览器自动化测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

import pytest

from src.tools import get_tool_meta, requires_confirmation
from src.tools.browser.config import load_browser_config
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
from src.tools.browser.session import (
    BrowserSessionManager,
    _safe_session_id,
    _validate_url,
    screenshot_dir,
)
from src.tools.browser.tools import (
    browser_fill,
    browser_get_page,
    browser_navigate,
)


class FakePage:
    """模拟 Playwright Page，避免单元测试启动真实浏览器。"""

    def __init__(self) -> None:
        self._url = "https://example.com/"
        self._title = "Example Domain"
        self.body_text = "Example Domain\nThis domain is for use in documentation examples."
        self.last_click = ""
        self.last_fill: tuple[str, str] = ("", "")
        self.last_press: tuple[str, str] = ("", "")
        self.scroll_delta = 0
        self.screenshot_path = ""
        self.wait_selector = ""

    @property
    def url(self) -> str:
        return self._url

    def goto(self, target: str, **kwargs) -> None:
        self._url = target

    def wait_for_load_state(self, state: str, **kwargs) -> None:
        pass

    def title(self) -> str:
        return self._title

    def click(self, selector: str, **kwargs) -> None:
        self.last_click = selector

    def fill(self, selector: str, value: str, **kwargs) -> None:
        self.last_fill = (selector, value)

    def press(self, selector: str, key: str) -> None:
        self.last_press = (selector, key)

    def inner_text(self, selector: str) -> str:
        if selector == "body":
            return self.body_text
        if selector == "#main":
            return "Main section"
        raise RuntimeError(f"selector not found: {selector}")

    def screenshot(self, path: str, **kwargs) -> None:
        self.screenshot_path = path
        Path(path).write_bytes(b"\x89PNG\r\n")

    def evaluate(self, script: str) -> None:
        if "scrollBy" in script:
            self.scroll_delta = int(script.split(",")[1].strip().rstrip(")"))

    def wait_for_timeout(self, ms: int) -> None:
        pass

    def wait_for_selector(self, selector: str, **kwargs) -> None:
        self.wait_selector = selector


class FakeManager:
    """替代 BrowserSessionManager，在单线程直接执行 page 回调。"""

    def __init__(self) -> None:
        self.page = FakePage()
        self.sessions: dict[str, FakePage] = {}
        self.closed: set[str] = set()

    def run(self, session_id: str, fn: Callable[[FakePage], Any]) -> Any:
        sid = _safe_session_id(session_id)
        if sid in self.closed:
            raise RuntimeError("session closed")
        page = self.sessions.setdefault(sid, FakePage())
        self.page = page
        return fn(page)

    def close(self, session_id: str) -> bool:
        sid = _safe_session_id(session_id)
        if sid not in self.sessions:
            return False
        self.closed.add(sid)
        del self.sessions[sid]
        return True

    def list_sessions(self) -> list[str]:
        return list(self.sessions.keys())

    def close_all(self) -> None:
        self.sessions.clear()
        self.closed.clear()


@pytest.fixture
def fake_mgr() -> FakeManager:
    mgr = FakeManager()
    with patch.object(BrowserSessionManager, "shared", return_value=mgr):
        yield mgr


@pytest.fixture(autouse=True)
def reset_browser_singleton():
    BrowserSessionManager._instance = None
    yield
    BrowserSessionManager._instance = None


# --- session 辅助 ---


def test_validate_url_accepts_https():
    assert _validate_url("https://example.com/path") == "https://example.com/path"


def test_validate_url_rejects_non_http():
    with pytest.raises(ValueError, match="无效 URL"):
        _validate_url("javascript:alert(1)")


def test_safe_session_id_sanitizes():
    assert _safe_session_id("  my/test  ") == "my_test"


def test_load_browser_config_has_defaults():
    cfg = load_browser_config()
    assert cfg["headless"] is True
    assert cfg["timeout_ms"] >= 1000
    assert "user_agent" in cfg


def test_screenshot_dir_creates_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.tools.browser.session.load_browser_config",
        lambda: {**load_browser_config(), "screenshot_dir": str(tmp_path / "shots")},
    )
    path = screenshot_dir()
    assert path.is_dir()


# --- core impl（mock page）---


def test_browser_navigate_impl(fake_mgr: FakeManager):
    out = browser_navigate_impl("https://example.com", session_id="t1")
    assert "已打开" in out
    assert fake_mgr.page._url == "https://example.com"


def test_browser_navigate_rejects_bad_url(fake_mgr: FakeManager):
    with pytest.raises(ValueError):
        browser_navigate_impl("not-a-url", session_id="t1")


def test_browser_get_page_impl(fake_mgr: FakeManager):
    browser_navigate_impl("https://example.com", session_id="t1")
    fake_mgr.sessions["t1"].body_text = "Hello browser test"
    out = browser_get_page_impl(session_id="t1")
    assert "Hello browser test" in out
    assert "Example Domain" in out


def test_browser_get_page_with_selector(fake_mgr: FakeManager):
    out = browser_get_page_impl(session_id="t1", selector="#main")
    assert "Main section" in out


def test_browser_click_impl(fake_mgr: FakeManager):
    out = browser_click_impl("button.submit", session_id="t1")
    assert "已点击" in out
    assert fake_mgr.page.last_click == "button.submit"


def test_browser_click_empty_selector(fake_mgr: FakeManager):
    assert "请提供 CSS 选择器" in browser_click_impl("", session_id="t1")


def test_browser_fill_impl(fake_mgr: FakeManager):
    out = browser_fill_impl("#q", "playwright test", session_id="t1", submit=True)
    assert "已填写并提交" in out
    assert fake_mgr.page.last_fill == ("#q", "playwright test")
    assert fake_mgr.page.last_press == ("#q", "Enter")


def test_browser_scroll_impl(fake_mgr: FakeManager):
    out = browser_scroll_impl(session_id="t1", direction="down", amount=500)
    assert "500" in out
    assert fake_mgr.page.scroll_delta == 500


def test_browser_wait_selector_impl(fake_mgr: FakeManager):
    out = browser_wait_selector_impl("#loaded", session_id="t1")
    assert "元素已出现" in out
    assert fake_mgr.page.wait_selector == "#loaded"


def test_browser_screenshot_impl(fake_mgr: FakeManager, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.tools.browser.core.screenshot_dir",
        lambda: tmp_path,
    )
    out = browser_screenshot_impl(session_id="t1", save_path="test-shot.png")
    assert "截图已保存" in out
    assert (tmp_path / "test-shot.png").is_file()


def test_browser_close_and_list_sessions(fake_mgr: FakeManager):
    browser_navigate_impl("https://example.com", session_id="sess-a")
    assert "sess-a" in fake_mgr.list_sessions()
    assert "sess-a" in browser_list_sessions_impl()
    assert "已关闭" in browser_close_impl("sess-a")
    assert browser_close_impl("sess-a").endswith("不存在或已关闭。")


# --- LangChain tool 包装 ---


def test_browser_navigate_tool_invoke(fake_mgr: FakeManager):
    out = browser_navigate.invoke({"url": "https://example.com", "session_id": "tool-s"})
    assert "已打开" in out


def test_browser_get_page_tool_invoke(fake_mgr: FakeManager):
    out = browser_get_page.invoke({"session_id": "tool-s"})
    assert "URL:" in out


def test_browser_fill_requires_confirmation():
    assert requires_confirmation("browser_fill") is True
    assert requires_confirmation("browser_navigate") is False


def test_browser_tools_meta_in_yaml():
    meta = get_tool_meta("browser_navigate")
    assert meta.get("enabled", True)
    assert meta.get("run_in_process") is False


def test_all_browser_tools_registered():
    from src.tools import ALL_TOOLS

    names = {t.name for t in ALL_TOOLS}
    expected = {
        "browser_navigate",
        "browser_get_page",
        "browser_click",
        "browser_fill",
        "browser_wait_selector",
        "browser_scroll",
        "browser_screenshot",
        "browser_close",
        "browser_list_sessions",
    }
    assert expected.issubset(names)


def test_sandbox_allows_browser_get_page_only():
    from src.tools.code.tool_rpc import sandbox_allowed_tools

    allowed = sandbox_allowed_tools()
    assert "browser_get_page" in allowed
    assert "browser_navigate" not in allowed
    assert "browser_fill" not in allowed


# --- Playwright 集成（本机有 Chromium 时运行）---


def _chromium_ready() -> bool:
    """检查 Chromium 可执行文件是否已安装（不启动浏览器）。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as p:
            exe = p.chromium.executable_path
        return bool(exe and Path(exe).is_file())
    except Exception:
        return False


@pytest.mark.browser_integration
@pytest.mark.skipif(not _chromium_ready(), reason="Chromium 未安装，请运行 playwright install chromium")
def test_playwright_integration_navigate_example():
    """真实打开 example.com，验证多步会话。"""
    sid = "pytest-integration"
    try:
        nav = browser_navigate_impl("https://example.com", session_id=sid)
        assert "example.com" in nav.lower()

        page_text = browser_get_page_impl(session_id=sid)
        assert "example" in page_text.lower()

        shot_dir = Path(load_browser_config()["screenshot_dir"])
        if not shot_dir.is_absolute():
            from src.infra.paths import INSTALL_ROOT

            shot_dir = (INSTALL_ROOT / shot_dir).resolve()
        shot_dir.mkdir(parents=True, exist_ok=True)
        shot_msg = browser_screenshot_impl(session_id=sid, save_path="pytest-example.png")
        assert "截图已保存" in shot_msg
        assert (shot_dir / "pytest-example.png").is_file()
    finally:
        browser_close_impl(sid)
        BrowserSessionManager.shared().close_all()
