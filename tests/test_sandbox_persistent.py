"""常驻代码沙箱 worker 测试。"""

from __future__ import annotations

from src.tools.code import sandbox
from src.tools.code.sandbox import (
    execute_code_in_sandbox,
    reset_code_session,
    shutdown_sandbox_workers,
)


def test_persistent_worker_reuses_process(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "_SESSION_DIR", tmp_path)
    monkeypatch.setenv("AGENT_SANDBOX_PERSISTENT", "1")
    monkeypatch.setattr(sandbox, "sandbox_tool_call_enabled", lambda: False)
    shutdown_sandbox_workers()
    reset_code_session("persist-a")

    out1 = execute_code_in_sandbox("x = 7\nprint(x)", session_id="persist-a")
    assert "7" in out1
    with sandbox._workers_lock:
        worker = sandbox._workers.get("persist-a")
        assert worker is not None
        proc1 = worker._proc
        assert proc1 is not None
        pid1 = proc1.pid

    out2 = execute_code_in_sandbox("print(x + 1)", session_id="persist-a")
    assert "8" in out2
    with sandbox._workers_lock:
        worker = sandbox._workers.get("persist-a")
        assert worker is not None
        assert worker._proc is not None
        assert worker._proc.pid == pid1

    shutdown_sandbox_workers()


def test_persistent_disabled_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "_SESSION_DIR", tmp_path)
    monkeypatch.setenv("AGENT_SANDBOX_PERSISTENT", "0")
    monkeypatch.setattr(sandbox, "sandbox_tool_call_enabled", lambda: False)
    shutdown_sandbox_workers()
    reset_code_session("oneshot")
    out1 = execute_code_in_sandbox("y = 3\nprint(y)", session_id="oneshot")
    assert "3" in out1
    out2 = execute_code_in_sandbox("print(y * 3)", session_id="oneshot")
    assert "9" in out2
    with sandbox._workers_lock:
        assert "oneshot" not in sandbox._workers


def test_shared_browser_runtime_reuses_launch(monkeypatch):
    """不启动真实 Chromium：验证多次 session 只 launch 一次。"""
    from src.tools.browser import session as browser_session

    launches = {"n": 0}
    contexts: list[object] = []

    class FakePage:
        def set_default_timeout(self, _ms: int) -> None:
            pass

    class FakeContext:
        def __init__(self) -> None:
            self.page = FakePage()

        def new_page(self) -> FakePage:
            return self.page

        def close(self) -> None:
            pass

    class FakeBrowser:
        def new_context(self, **_kwargs):
            ctx = FakeContext()
            contexts.append(ctx)
            return ctx

        def close(self) -> None:
            pass

    class FakeChromium:
        def launch(self, **_kwargs):
            launches["n"] += 1
            return FakeBrowser()

    class FakePlaywright:
        def __init__(self) -> None:
            self.chromium = FakeChromium()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        "playwright.sync_api.sync_playwright",
        lambda: FakePlaywright(),
    )
    monkeypatch.setattr(
        "src.tools.browser.media.install_media_blocker",
        lambda _page: None,
    )

    runtime = browser_session._SharedBrowserRuntime()
    assert launches["n"] == 1

    def touch(page):
        return "ok"

    assert runtime.run("s1", touch) == "ok"
    assert runtime.run("s2", touch) == "ok"
    assert launches["n"] == 1
    assert len(contexts) == 2
    assert runtime.close_session("s1") is True
    runtime.shutdown()
