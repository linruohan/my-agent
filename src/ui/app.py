"""应用入口：pywebview 桌面 UI。"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from loguru import logger

from src.infra.paths import DIST_DIR, LEGACY_WEB_DIR, app_icon_path
from src.infra.process_executor import shutdown_process_pools
from src.ui.app_api import AppApi
from src.ui.controller import AssistantController


def resolve_web_index() -> Path:
    """选择前端入口（本地文件）。

    - AGENT_UI=legacy|classic|old → 强制旧版 legacy/web/index.html
    - AGENT_UI=react|new → 强制 dist/web/index.html（需先 npm run build）
    - 未设置时：若 dist/web/index.html 存在则用 React UI，否则旧版

    注意：AGENT_UI=dev|vite|hmr 请用 resolve_web_url()，不走本函数返回值。
    """
    ui = os.environ.get("AGENT_UI", "").strip().lower()
    dist_index = DIST_DIR / "index.html"
    legacy_index = LEGACY_WEB_DIR / "index.html"

    if ui in ("legacy", "classic", "old"):
        return legacy_index
    if ui in ("react", "new", "1", "true", "yes"):
        if not dist_index.is_file():
            raise FileNotFoundError(
                f"React UI 未构建: {dist_index}（请在 frontend/ 执行 npm run build）"
            )
        return dist_index
    if dist_index.is_file():
        return dist_index
    return legacy_index


def resolve_web_url() -> str:
    """返回 pywebview 加载地址：dev 模式下为 Vite URL，否则为本地 file URI。"""
    ui = os.environ.get("AGENT_UI", "").strip().lower()
    if ui in ("dev", "vite", "hmr"):
        return os.environ.get("AGENT_UI_DEV_URL", "http://127.0.0.1:5173").rstrip("/")
    return resolve_web_index().as_uri()

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
    from src.agent.learning_dedupe import shared_ledger
    from src.memory.conversation_index import shared_conversation_index
    from src.database import close_database

    shared_conversation_index().close()
    shared_ledger().close()
    close_database()
    shutdown_process_pools(wait=True)
    if controller._graph_bundle:
        controller._graph_bundle.close()


def _finalize_exit(controller: AssistantController, poll_thread: threading.Thread) -> None:
    _shutdown_controller(controller)
    poll_thread.join(timeout=2.0)
    logger.info("应用已退出")
    os._exit(0)


def run_app() -> None:
    """启动桌面 UI（React dist/ 或 legacy/web）+ pywebview。"""
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError("需要安装 pywebview：pip install pywebview") from exc

    web_url = resolve_web_url()
    if web_url.startswith("file:"):
        web_index = resolve_web_index()
        if not web_index.exists():
            raise FileNotFoundError(f"Web UI 未找到: {web_index}")

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

    logger.info("加载 Web UI: {}", web_url)
    window = webview.create_window(
        title,
        url=web_url,
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
