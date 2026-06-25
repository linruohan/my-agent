"""定时任务执行与结果投递。"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from loguru import logger

from src.automation.schedule import compute_next_run
from src.automation.store import CronJob
from src.ui.skill.runner import run_skill


def execute_cron_job(
    job: CronJob,
    *,
    graph: Any | None = None,
    on_deliver: Callable[[CronJob, str], None] | None = None,
) -> str:
    """执行单个定时任务，返回结果摘要。"""
    action = job.action or {}
    try:
        if job.action_type == "notify":
            message = str(action.get("message") or job.name).strip()
            result = message or "（空消息）"
        elif job.action_type == "skill":
            skill_name = str(action.get("skill_name") or "").strip()
            args = str(action.get("args") or "")
            if not skill_name:
                return "失败：未指定 skill_name"
            skill_result = run_skill(skill_name, args, llm=None)
            if skill_result.ok:
                result = (skill_result.output or "Skill 执行成功").strip()
            else:
                result = f"Skill 失败：{skill_result.error or '未知错误'}"
        elif job.action_type == "agent":
            prompt = str(action.get("prompt") or "").strip()
            if not prompt:
                return "失败：未指定 agent prompt"
            if graph is None:
                return "失败：Agent 未就绪"
            from src.automation.agent_sync import run_agent_sync

            thread_id = f"cron-{job.id}-{uuid.uuid4().hex[:8]}"
            result = run_agent_sync(graph, prompt, thread_id)
        else:
            return f"失败：未知 action_type {job.action_type}"
    except Exception as exc:
        logger.exception("定时任务执行失败: {}", job.name)
        result = f"执行异常：{exc}"

    if on_deliver:
        try:
            on_deliver(job, result)
        except Exception:
            logger.exception("定时任务投递失败: {}", job.name)
    return result


def advance_job_schedule(job: CronJob, *, now_iso: str) -> str | None:
    """计算并返回下次运行 ISO 时间。"""
    nxt = compute_next_run(job.schedule)
    if nxt is None:
        return None
    return nxt.isoformat()
