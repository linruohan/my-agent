"""应用入口：pywebview 桌面 UI。"""

from __future__ import annotations

import os
import threading

from loguru import logger

from src.infra.paths import WEB_DIR
from src.infra.process_executor import shutdown_process_pools
from src.ui.app_api import AppApi
from src.ui.controller import AssistantController

WEB_INDEX = WEB_DIR / "index.html"


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


def _shutdown_controller(controller: AssistantController) -> None:
    stop = controller._poll_stop
    stop.set()
    controller._task_reminder.stop()
    controller._cron_scheduler.stop()
    controller._cron_store.close()
    controller._gateway.stop()
    controller._gateway_inbox.close()
    from src.tools.browser.session import BrowserSessionManager

    BrowserSessionManager.shared().close_all()
    controller._session_store.close()
    controller._task_store.close()
    controller._note_store.close()
    controller._search_cache.close()
    from src.infra.metrics import close_metrics_store

    close_metrics_store()
    shutdown_process_pools(wait=False)
    if controller._graph_bundle:
        controller._graph_bundle.close()


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
    logger.info("WebView 窗口启动中…")
    try:
        webview.start(debug=webview_debug)
    finally:
        _shutdown_controller(controller)
