"""应用入口：pywebview 桌面 UI。"""

from __future__ import annotations

import os
import threading

from loguru import logger

from src.infra.paths import WEB_DIR, app_icon_path
from src.infra.process_executor import shutdown_process_pools
from src.ui.app_api import AppApi
from src.ui.controller import AssistantController

WEB_INDEX = WEB_DIR / "index.html"

_shutdown_lock = threading.Lock()
_shutdown_done = False


def _poll_loop(controller: AssistantController, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            controller.poll_agent_events()
        except Exception:
            logger.exception("事件轮询异常")
        runner = controller.runner
        if runner.event_queue.empty():
            runner.event_notify.wait(timeout=0.5)
            runner.event_notify.clear()


def _interrupt_background_work(controller: AssistantController) -> None:
    controller._poll_stop.set()
    controller._compose_cancel.set()
    runner = getattr(controller, "runner", None)
    if runner is not None:
        runner.stop()


def _shutdown_controller(controller: AssistantController) -> None:
    global _shutdown_done
    with _shutdown_lock:
        if _shutdown_done:
            return
        _shutdown_done = True

    logger.debug("正在关闭后台服务…")
    _interrupt_background_work(controller)
    controller._task_reminder.stop()
    controller._cron_scheduler.stop()
    controller._cron_store.close()
    controller._gateway.stop()
    controller._gateway_inbox.close()
    from src.tools.browser.session import BrowserSessionManager

    BrowserSessionManager.shared().shutdown()
    controller._session_store.close()
    controller._task_store.close()
    controller._note_store.close()
    controller._search_cache.close()
    from src.infra.metrics import close_metrics_store

    close_metrics_store()
    shutdown_process_pools(wait=True)
    if controller._graph_bundle:
        controller._graph_bundle.close()


def _finalize_exit(controller: AssistantController, poll_thread: threading.Thread) -> None:
    _shutdown_controller(controller)
    poll_thread.join(timeout=2.0)
    logger.info("应用已退出")
    os._exit(0)


def run_app() -> None:
    """启动内置 web/ + pywebview 桌面 UI。"""
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError("需要安装 pywebview：pip install pywebview") from exc

    if not WEB_INDEX.exists():
        raise FileNotFoundError(f"Web UI 未找到: {WEB_INDEX}")

    controller = AssistantController()
    api = AppApi(controller)
    app_cfg = controller.app_cfg.get("app", {})
    w = int(app_cfg.get("window_width", 1100))
    h = int(app_cfg.get("window_height", 720))
    title = app_cfg.get("title", "个人助理 Agent")
    webview_debug = os.environ.get("AGENT_WEBVIEW_DEBUG", "").lower() in ("1", "true", "yes")

    stop = controller._poll_stop
    poll_thread = threading.Thread(
        target=_poll_loop,
        args=(controller, stop),
        daemon=True,
        name="agent-event-poll",
    )
    poll_thread.start()

    window = webview.create_window(
        title,
        url=WEB_INDEX.as_uri(),
        js_api=api,
        width=w,
        height=h,
        min_size=(800, 560),
    )
    controller.attach_window(window)

    def on_closing() -> None:
        _interrupt_background_work(controller)

    def on_closed() -> None:
        threading.Thread(
            target=_finalize_exit,
            args=(controller, poll_thread),
            daemon=True,
            name="app-exit",
        ).start()

    window.events.closing += on_closing
    window.events.closed += on_closed

    logger.info("WebView 窗口启动中…")
    icon = app_icon_path()
    start_kwargs: dict[str, object] = {"debug": webview_debug}
    if icon is not None:
        start_kwargs["icon"] = str(icon)
    try:
        webview.start(**start_kwargs)
    finally:
        _finalize_exit(controller, poll_thread)
