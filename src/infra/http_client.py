"""进程内共享 httpx.Client，避免热路径反复 TLS/连接池冷启动。"""

from __future__ import annotations

import atexit
import threading

import httpx

_lock = threading.Lock()
_client: httpx.Client | None = None


def shared_http_client(*, timeout: float = 30.0) -> httpx.Client:
    """返回进程级复用的 Client；单次请求可用 timeout/headers 覆盖。"""
    global _client
    with _lock:
        if _client is None or _client.is_closed:
            _client = httpx.Client(timeout=timeout, follow_redirects=True)
        return _client


def close_shared_http_client() -> None:
    global _client
    with _lock:
        if _client is not None and not _client.is_closed:
            try:
                _client.close()
            except Exception:
                pass
        _client = None


atexit.register(close_shared_http_client)
