"""定时任务 Toast 通知。"""

from __future__ import annotations

import sys

from loguru import logger


def send_cron_toast(title: str, message: str) -> bool:
    title = (title or "定时任务").strip()
    message = (message or "").strip()[:500]
    if sys.platform != "win32":
        logger.info("[cron] {} — {}", title, message)
        return False
    try:
        from win11toast import notify

        notify(title, message, app_id="my-agent")
        return True
    except Exception as exc:
        logger.warning("Cron Toast 失败: {}", exc)
        return False
