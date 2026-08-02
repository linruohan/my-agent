"""Playwright 浏览器会话管理：进程内共享 Chromium，每逻辑 session 独立 Context。"""

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


class _SharedBrowserRuntime:
    """单线程持有 Chromium；各 session 使用独立 BrowserContext + Page。"""

    def __init__(self) -> None:
        self._cfg = load_browser_config()
        self._queue: queue.Queue[Any] = queue.Queue()
        self._ready = threading.Event()
        self._boot_error: str | None = None
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="browser-shared-runtime",
        )
        self._thread.start()
        if not self._ready.wait(timeout=90):
            raise RuntimeError(
                "浏览器启动超时。请确认已安装 Chromium：playwright install chromium"
            )
        if self._boot_error:
            raise RuntimeError(self._boot_error)

    def run(self, session_id: str, fn: Callable[[_TYPE_PAGE], Any], *, timeout: float = 120) -> Any:
        holder: list[Any] = [None, None]
        done = threading.Event()
        self._queue.put(("run", session_id, fn, holder, done))
        if not done.wait(timeout=timeout):
            raise TimeoutError(f"浏览器操作超时（>{timeout}s）")
        if holder[1] is not None:
            raise holder[1]
        return holder[0]

    def close_session(self, session_id: str) -> bool:
        holder: list[Any] = [False]
        done = threading.Event()
        self._queue.put(("close", session_id, holder, done))
        done.wait(timeout=30)
        return bool(holder[0])

    def list_sessions(self) -> list[str]:
        holder: list[Any] = [[]]
        done = threading.Event()
        self._queue.put(("list", holder, done))
        done.wait(timeout=10)
        return list(holder[0] or [])

    def shutdown(self) -> None:
        self._queue.put(None)
        self._thread.join(timeout=30)

    def _loop(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            self._boot_error = f"Playwright 未安装: {exc}"
            self._ready.set()
            return

        from src.tools.browser.media import install_media_blocker

        contexts: dict[str, tuple[Any, Any]] = {}
        try:
            with sync_playwright() as p:
                launch_kwargs: dict[str, Any] = {"headless": self._cfg["headless"]}
                args = self._cfg.get("chromium_args") or []
                if args:
                    launch_kwargs["args"] = list(args)
                browser = p.chromium.launch(**launch_kwargs)
                logger.info("Browser 共享 Chromium 已启动")
                self._ready.set()
                while True:
                    item = self._queue.get()
                    if item is None:
                        break
                    op = item[0]
                    if op == "run":
                        _, sid, fn, holder, done = item
                        try:
                            if sid not in contexts:
                                ctx = browser.new_context(user_agent=self._cfg["user_agent"])
                                page = ctx.new_page()
                                page.set_default_timeout(self._cfg["timeout_ms"])
                                if self._cfg.get("block_media", True):
                                    install_media_blocker(page)
                                contexts[sid] = (ctx, page)
                            holder[0] = fn(contexts[sid][1])
                        except Exception as exc:
                            holder[1] = exc
                        finally:
                            done.set()
                    elif op == "close":
                        _, sid, holder, done = item
                        pair = contexts.pop(sid, None)
                        if pair is not None:
                            try:
                                pair[0].close()
                            except Exception:
                                logger.debug("关闭 BrowserContext 失败 sid={}", sid, exc_info=True)
                            holder[0] = True
                        done.set()
                    elif op == "list":
                        _, holder, done = item
                        holder[0] = list(contexts.keys())
                        done.set()
                for sid, (ctx, _) in list(contexts.items()):
                    try:
                        ctx.close()
                    except Exception:
                        pass
                contexts.clear()
                browser.close()
                logger.debug("Browser 共享 Chromium 已关闭")
        except Exception as exc:
            logger.exception("共享浏览器运行时异常")
            if not self._ready.is_set():
                self._boot_error = str(exc)
                self._ready.set()


class BrowserSessionManager:
    _instance: BrowserSessionManager | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._runtime: _SharedBrowserRuntime | None = None
        self._runtime_lock = threading.Lock()
        self._sessions: dict[str, float] = {}  # sid -> last_used
        self._lock = threading.Lock()
        self._cfg = load_browser_config()
        self._cleanup_stop = threading.Event()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="browser-idle-cleanup",
        )
        self._cleanup_thread.start()

    def _ensure_runtime(self) -> _SharedBrowserRuntime:
        with self._runtime_lock:
            if self._runtime is None:
                self._runtime = _SharedBrowserRuntime()
            return self._runtime

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
        oldest_sid = min(self._sessions, key=lambda sid: self._sessions[sid])
        self._sessions.pop(oldest_sid, None)
        logger.info("Browser 会话数达上限，驱逐最旧会话 {}", oldest_sid)
        runtime = self._runtime
        if runtime is not None:
            runtime.close_session(oldest_sid)

    def run(self, session_id: str, fn: Callable[[_TYPE_PAGE], Any]) -> Any:
        sid = _safe_session_id(session_id)
        with self._lock:
            if sid not in self._sessions:
                self._evict_oldest_if_needed()
            self._sessions[sid] = time.monotonic()
        return self._ensure_runtime().run(sid, fn)

    def close(self, session_id: str) -> bool:
        sid = _safe_session_id(session_id)
        with self._lock:
            existed = sid in self._sessions
            self._sessions.pop(sid, None)
        runtime = self._runtime
        if runtime is None:
            return existed
        closed = runtime.close_session(sid)
        return closed or existed

    def close_all(self) -> None:
        with self._lock:
            sids = list(self._sessions.keys())
            self._sessions.clear()
        runtime = self._runtime
        if runtime is None:
            return
        for sid in sids:
            runtime.close_session(sid)

    def shutdown(self) -> None:
        """停止空闲清理线程并关闭共享 Chromium。"""
        self._cleanup_stop.set()
        self.close_all()
        with self._runtime_lock:
            runtime = self._runtime
            self._runtime = None
        if runtime is not None:
            runtime.shutdown()

    def cleanup_idle(self) -> int:
        """关闭空闲超时的会话 Context（保留共享 Chromium）。"""
        limit = float(self._cfg.get("idle_close_sec", 600))
        now = time.monotonic()
        closed = 0
        with self._lock:
            stale = [sid for sid, ts in self._sessions.items() if now - ts > limit]
            for sid in stale:
                self._sessions.pop(sid, None)
        runtime = self._runtime
        if runtime is None:
            return 0
        for sid in stale:
            if runtime.close_session(sid):
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
