"""LangChain 工具：定时任务（自动化网关）管理。"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from src.automation.schedule import compute_next_run, format_schedule
from src.automation.delivery import format_delivery_label, resolve_cron_delivery
from src.automation.store import CronJobStore


def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


@tool
def list_cron_jobs(include_disabled: bool = True) -> str:
    """列出所有定时任务（自动化网关）。

    Args:
        include_disabled: 是否包含已暂停任务，默认 True
    """
    jobs = CronJobStore().list_all(enabled_only=not include_disabled)
    if not jobs:
        return "当前没有定时任务。"
    lines = [f"共 {len(jobs)} 个定时任务："]
    for j in jobs:
        status = "启用" if j.enabled else "暂停"
        nxt = j.next_run_at[:16] if j.next_run_at else "未排程"
        lines.append(
            f"- [{j.id[:8]}] {j.name}（{status}）"
            f" | {j.action_type} | {format_schedule(j.schedule)}"
            f" | 投递 {format_delivery_label(j.delivery)} | 下次 {nxt}"
        )
    return "\n".join(lines)


@tool
def add_cron_job(
    name: str,
    action_type: str,
    action_json: str,
    schedule_json: str,
    delivery: str = "toast",
) -> str:
    """添加定时任务。action_type: notify | skill | agent。

    schedule_json 示例：
    - 每 60 分钟：{"type":"interval","minutes":60}
    - 每天 9:00：{"type":"daily","hour":9,"minute":0}
    - cron：{"type":"cron","expr":"0 9 * * *"}

    action_json 示例：
    - notify：{"message":"早安摘要"}
    - skill：{"skill_name":"my-skill","args":"..."}
    - agent：{"prompt":"总结今日未完成任务并给出建议"}

    Args:
        name: 任务名称
        action_type: notify / skill / agent
        action_json: JSON 字符串
        schedule_json: JSON 字符串
        delivery: toast、session、gateway（使用 gateway.cron_default 配置）、
            default（同 gateway），或 gateway:SOURCE:CHAT_ID
            例如 gateway:telegram:123456789
    """
    action = _parse_json(action_json)
    schedule = _parse_json(schedule_json)
    if not schedule.get("type"):
        return "schedule_json 无效，需包含 type 字段。"
    at = (action_type or "").strip().lower()
    if at not in ("notify", "skill", "agent"):
        return "action_type 须为 notify、skill 或 agent。"
    normalized_delivery = resolve_cron_delivery(delivery)
    if not normalized_delivery:
        return (
            "delivery 无效。支持 toast、session、gateway/default（需配置 gateway.cron_default），"
            "或 gateway:SOURCE:CHAT_ID。"
        )
    nxt = compute_next_run(schedule)
    store = CronJobStore()
    job = store.add(
        name=name,
        action_type=at,
        action=action,
        schedule=schedule,
        delivery=normalized_delivery,
        next_run_at=nxt.isoformat() if nxt else None,
    )
    return (
        f"已创建定时任务 #{job.id[:8]}「{job.name}」"
        f"，类型 {at}，{format_schedule(schedule)}"
        f"，投递 {format_delivery_label(normalized_delivery)}"
        f"，下次运行 {job.next_run_at or '未排程'}。"
    )


@tool
def pause_cron_job(job_id: str) -> str:
    """暂停定时任务。

    Args:
        job_id: 任务 ID（完整 UUID 或前 8 位前缀）
    """
    store = CronJobStore()
    job = _resolve_job(store, job_id)
    if not job:
        return f"未找到任务：{job_id}"
    store.set_enabled(job.id, False)
    return f"已暂停「{job.name}」。"


@tool
def resume_cron_job(job_id: str) -> str:
    """恢复已暂停的定时任务。

    Args:
        job_id: 任务 ID
    """
    store = CronJobStore()
    job = _resolve_job(store, job_id)
    if not job:
        return f"未找到任务：{job_id}"
    nxt = compute_next_run(job.schedule)
    store.set_enabled(job.id, True)
    if nxt:
        store.set_next_run(job.id, nxt.isoformat())
    return f"已恢复「{job.name}」，下次运行 {nxt.isoformat() if nxt else '未排程'}。"


@tool
def delete_cron_job(job_id: str) -> str:
    """删除定时任务。敏感操作，执行前需用户确认。

    Args:
        job_id: 任务 ID
    """
    store = CronJobStore()
    job = _resolve_job(store, job_id)
    if not job:
        return f"未找到任务：{job_id}"
    store.delete(job.id)
    return f"已删除「{job.name}」。"


def _resolve_job(store: CronJobStore, job_id: str):
    jid = (job_id or "").strip()
    if not jid:
        return None
    job = store.get(jid)
    if job:
        return job
    prefix = jid.lower()
    for item in store.list_all():
        if item.id.lower().startswith(prefix):
            return item
    return None


AUTOMATION_TOOLS = [list_cron_jobs, add_cron_job, pause_cron_job, resume_cron_job, delete_cron_job]
