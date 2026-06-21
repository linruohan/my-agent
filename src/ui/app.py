"""pywebview 应用入口。"""

from __future__ import annotations

import threading

import webview
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


def run_app() -> None:
    import os

    if not WEB_INDEX.exists():
        raise FileNotFoundError(f"Web UI 未找到: {WEB_INDEX}")

    controller = AssistantController()
    api = AppApi(controller)
    app_cfg = controller.app_cfg.get("app", {})
    w = int(app_cfg.get("window_width", 1100))
    h = int(app_cfg.get("window_height", 720))
    title = app_cfg.get("title", "个人助理 Agent")
    webview_debug = os.environ.get("AGENT_WEBVIEW_DEBUG", "").lower() in ("1", "true", "yes")
    if webview_debug:
        logger.info("[voice] WebView debug 已开启（F12 可开开发者工具）")

    window = webview.create_window(
        title,
        url=WEB_INDEX.as_uri(),
        js_api=api,
        width=w,
        height=h,
        min_size=(800, 560),
    )
    controller.attach_window(window)

    stop = controller._poll_stop
    poll_thread = threading.Thread(
        target=_poll_loop,
        args=(controller, stop),
        daemon=True,
        name="agent-event-poll",
    )
    poll_thread.start()

    logger.info("WebView 窗口启动中…")
    try:
        webview.start(debug=webview_debug)
    finally:
        stop.set()
        controller._task_reminder.stop()
        controller._session_store.close()
        controller._task_store.close()
        controller._note_store.close()
        controller._search_cache.close()
        from src.infra.metrics import close_metrics_store

        close_metrics_store()
        shutdown_process_pools(wait=False)
        if controller._graph_bundle:
            controller._graph_bundle.close()
