"""Playwright 浏览器会话管理（每 session 独立线程）。"""

from __future__ import annotations

import queue
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from loguru import logger

from src.infra.paths import INSTALL_ROOT
from src.tools.browser.config import load_browser_config

_TYPE_PAGE = Any


def _validate_url(url: str) -> str:
    u = (url or "").strip()
    parsed = urlparse(u)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"无效 URL：{url}")
    return u


def _safe_session_id(session_id: str) -> str:
    sid = (session_id or "default").strip() or "default"
    return re.sub(r"[^\w.-]", "_", sid)[:64]


class _BrowserSession:
    """在专用线程内持有 Playwright 浏览器与 Page。"""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._cfg = load_browser_config()
        self._queue: queue.Queue[Any] = queue.Queue()
        self._ready = threading.Event()
        self._closed = threading.Event()
        self._last_used = time.monotonic()
        self._current_url = ""
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name=f"browser-{session_id[:12]}",
        )
        self._thread.start()
        if not self._ready.wait(timeout=90):
            raise RuntimeError(
                "浏览器启动超时。请确认已安装 Chromium：playwright install chromium"
            )

    def touch(self) -> None:
        self._last_used = time.monotonic()

    @property
    def last_used(self) -> float:
        return self._last_used

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._queue.put(None)
        self._closed.set()

    def run(self, fn: Callable[[_TYPE_PAGE], Any], *, timeout: float = 120) -> Any:
        if self._closed.is_set():
            raise RuntimeError(f"浏览器会话「{self.session_id}」已关闭")
        self.touch()
        holder: list[Any] = [None, None]
        done = threading.Event()
        self._queue.put((fn, holder, done))
        if not done.wait(timeout=timeout):
            raise TimeoutError(f"浏览器操作超时（>{timeout}s）")
        if holder[1] is not None:
            raise holder[1]
        return holder[0]

    def _loop(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            self._ready.set()
            logger.error("Playwright 未安装: {}", exc)
            return

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self._cfg["headless"])
                page = browser.new_page(user_agent=self._cfg["user_agent"])
                page.set_default_timeout(self._cfg["timeout_ms"])
                self._ready.set()
                while True:
                    item = self._queue.get()
                    if item is None:
                        break
                    fn, holder, done = item
                    try:
                        holder[0] = fn(page)
                    except Exception as exc:
                        holder[1] = exc
                    finally:
                        done.set()
                browser.close()
        except Exception:
            logger.exception("浏览器会话 {} 异常", self.session_id)
            self._ready.set()


class BrowserSessionManager:
    _instance: BrowserSessionManager | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._sessions: dict[str, _BrowserSession] = {}
        self._lock = threading.Lock()
        self._cfg = load_browser_config()
        self._cleanup_stop = threading.Event()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="browser-idle-cleanup",
        )
        self._cleanup_thread.start()

    def _cleanup_loop(self) -> None:
        interval = float(self._cfg.get("idle_cleanup_interval_sec", 120))
        while not self._cleanup_stop.is_set():
            try:
                closed = self.cleanup_idle()
                if closed:
                    logger.debug("Browser 空闲清理：关闭 {} 个会话", closed)
            except Exception:
                logger.exception("Browser 空闲清理失败")
            self._cleanup_stop.wait(interval)

    @classmethod
    def shared(cls) -> BrowserSessionManager:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _evict_oldest_if_needed(self) -> None:
        max_sessions = int(self._cfg.get("max_sessions", 8))
        if len(self._sessions) < max_sessions:
            return
        oldest_sid = min(self._sessions, key=lambda sid: self._sessions[sid].last_used)
        session = self._sessions.pop(oldest_sid, None)
        if session:
            logger.info("Browser 会话数达上限，驱逐最旧会话 {}", oldest_sid)
            session.close()

    def _get(self, session_id: str) -> _BrowserSession:
        sid = _safe_session_id(session_id)
        with self._lock:
            session = self._sessions.get(sid)
            if session is None or session._closed.is_set():
                self._evict_oldest_if_needed()
                session = _BrowserSession(sid)
                self._sessions[sid] = session
            session.touch()
            return session

    def run(self, session_id: str, fn: Callable[[_TYPE_PAGE], Any]) -> Any:
        return self._get(session_id).run(fn)

    def close(self, session_id: str) -> bool:
        sid = _safe_session_id(session_id)
        with self._lock:
            session = self._sessions.pop(sid, None)
        if session:
            session.close()
            return True
        return False

    def close_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.close()

    def cleanup_idle(self) -> int:
        """关闭空闲超时的会话。"""
        limit = float(self._cfg.get("idle_close_sec", 600))
        now = time.monotonic()
        closed = 0
        with self._lock:
            stale = [sid for sid, s in self._sessions.items() if now - s.last_used > limit]
            for sid in stale:
                session = self._sessions.pop(sid, None)
                if session:
                    session.close()
                    closed += 1
        return closed

    def list_sessions(self) -> list[str]:
        with self._lock:
            return list(self._sessions.keys())


def screenshot_dir() -> Path:
    cfg = load_browser_config()
    rel = cfg.get("screenshot_dir", "data/workspace/browser_screenshots")
    path = Path(rel)
    if not path.is_absolute():
        path = (INSTALL_ROOT / rel).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_browser_url(url: str) -> str:
    return _validate_url(url)
