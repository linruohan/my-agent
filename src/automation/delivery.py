"""定时任务结果投递：Toast / 会话 / Gateway 通道。"""

from __future__ import annotations

from typing import Callable

from loguru import logger

from src.automation.notify import send_cron_toast
from src.automation.store import CronJob


def parse_gateway_delivery(delivery: str) -> tuple[str, str] | None:
    """解析 gateway:telegram:123456 格式，返回 (source, chat_id)。"""
    text = (delivery or "").strip()
    if not text.startswith("gateway:"):
        return None
    parts = text.split(":", 2)
    if len(parts) != 3:
        return None
    source = parts[1].strip()
    chat_id = parts[2].strip()
    if not source or not chat_id:
        return None
    return source, chat_id


def default_gateway_delivery() -> str | None:
    """读取 gateway.cron_default 配置，返回 gateway:SOURCE:CHAT_ID。"""
    from src.gateway.config import load_gateway_config

    cfg = load_gateway_config()
    cron = cfg.get("cron_default") or {}
    source = str(cron.get("source") or "").strip()
    chat_id = str(cron.get("chat_id") or "").strip()
    if source and chat_id:
        return f"gateway:{source}:{chat_id}"
    return None


def resolve_cron_delivery(delivery: str) -> str | None:
    """解析 Cron delivery，支持 default/gateway 使用全局默认 Gateway 目标。"""
    raw = (delivery or "toast").strip()
    lowered = raw.lower()
    if lowered in ("default", "gateway"):
        resolved = default_gateway_delivery()
        return resolved
    if lowered == "":
        return "toast"
    return normalize_delivery(raw)


def normalize_delivery(delivery: str) -> str | None:
    """校验 delivery 字符串，无效时返回 None。"""
    d = (delivery or "toast").strip().lower()
    if d in ("toast", "session"):
        return d
    if parse_gateway_delivery(d):
        return d
    return None


def format_delivery_label(delivery: str) -> str:
    d = (delivery or "toast").strip()
    if d in ("toast", "session"):
        return d
    parsed = parse_gateway_delivery(d)
    if parsed:
        return f"gateway/{parsed[0]}/{parsed[1]}"
    return d


def deliver_cron_result(
    job: CronJob,
    result: str,
    *,
    gateway_deliver: Callable[[str, str, str], None] | None = None,
    session_handler: Callable[[CronJob, str], None] | None = None,
) -> None:
    """按 job.delivery 投递定时任务结果。"""
    delivery = (job.delivery or "toast").strip()
    title = f"⏰ {job.name}"
    body = (result or "").strip()
    message = f"{title}\n{body}" if body else title

    if delivery == "toast":
        send_cron_toast(title, body[:400])
        return

    if delivery == "session":
        if session_handler:
            session_handler(job, result)
        else:
            logger.warning("定时任务「{}」delivery=session 但未配置 session_handler", job.name)
        return

    parsed = parse_gateway_delivery(delivery)
    if parsed:
        source, chat_id = parsed
        if gateway_deliver:
            gateway_deliver(source, chat_id, message)
        else:
            logger.warning(
                "定时任务「{}」delivery={} 但 Gateway 未就绪，结果未投递",
                job.name,
                delivery,
            )
        return

    logger.warning("定时任务「{}」未知 delivery={}，回退 Toast", job.name, delivery)
    send_cron_toast(title, body[:400])
