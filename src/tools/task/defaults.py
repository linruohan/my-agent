"""任务添加时的默认值（负责人、截止、提醒）。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from src.infra.user_settings import load_user_settings
from src.tools.task.parse import calc_remind_at, parse_due_datetime

DEFAULT_OWNER_NAME = "林若寒"
DEFAULT_DUE_HOUR = 17
DEFAULT_DUE_MINUTE = 30
DEFAULT_REMIND_SPEC = "prevday:09:00,14:30,16:30"
DEFAULT_PREVDAY_REMIND_TIMES = ((9, 0), (14, 30), (16, 30))


def get_default_owner_name() -> str:
    settings = load_user_settings()
    tasks = settings.get("tasks") or {}
    name = str(tasks.get("owner_name") or DEFAULT_OWNER_NAME).strip()
    return name or DEFAULT_OWNER_NAME


def default_due_datetime(ref: datetime | None = None) -> datetime:
    ref = ref or datetime.now().astimezone()
    return ref.replace(
        hour=DEFAULT_DUE_HOUR,
        minute=DEFAULT_DUE_MINUTE,
        second=0,
        microsecond=0,
    )


def calc_prevday_remind_times(due: datetime) -> list[datetime]:
    prev = due.date() - timedelta(days=1)
    tz = due.tzinfo or datetime.now().astimezone().tzinfo
    return [
        datetime(prev.year, prev.month, prev.day, h, m, tzinfo=tz)
        for h, m in DEFAULT_PREVDAY_REMIND_TIMES
    ]


def build_remind_schedule(
    due: datetime,
    remind_spec: str | None,
    *,
    ref: datetime | None = None,
) -> list[str]:
    """根据 remind_spec 生成提醒时间列表（仅保留 ref 之后的时刻）。"""
    ref = ref or datetime.now().astimezone()
    spec = (remind_spec or "").strip()
    if not spec or spec == DEFAULT_REMIND_SPEC or spec == "default":
        candidates = calc_prevday_remind_times(due)
    elif spec.startswith("prevday:"):
        parts = spec.split(":", 1)[1]
        tz = due.tzinfo or ref.tzinfo
        prev = due.date() - timedelta(days=1)
        candidates = []
        for chunk in parts.split(","):
            chunk = chunk.strip()
            if not chunk or ":" not in chunk:
                continue
            h_s, m_s = chunk.split(":", 1)
            candidates.append(
                datetime(prev.year, prev.month, prev.day, int(h_s), int(m_s), tzinfo=tz)
            )
    else:
        try:
            return [calc_remind_at(due, spec).isoformat()]
        except ValueError:
            return []

    future = sorted(d for d in candidates if d > ref)
    if not future and (spec in ("", DEFAULT_REMIND_SPEC, "default") or spec.startswith("prevday:")):
        fallback = calc_remind_at(due, "1h")
        if fallback > ref:
            future = [fallback]
    return [d.isoformat() for d in future]


def next_remind_from_schedule(schedule: list[str], *, ref: datetime | None = None) -> str | None:
    ref = ref or datetime.now().astimezone()
    future = []
    for iso in schedule:
        try:
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.astimezone()
            if dt > ref:
                future.append(dt)
        except ValueError:
            continue
    if not future:
        return None
    return min(future).isoformat()


def append_remind_to_schedule(
    schedule: list[str] | None,
    iso: str,
    *,
    ref: datetime | None = None,
) -> tuple[list[str], str | None]:
    """向提醒计划追加一个具体时间点，返回排序后的计划与下一次提醒。"""
    ref = ref or datetime.now().astimezone()
    merged: list[str] = list(schedule or [])
    if iso and iso not in merged:
        merged.append(iso)

    def _sort_key(s: str) -> datetime:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.astimezone()
        return dt

    merged.sort(key=_sort_key)
    return merged, next_remind_from_schedule(merged, ref=ref)


def apply_add_defaults(fields: dict[str, Any], *, ref: datetime | None = None) -> dict[str, Any]:
    """为 /tsk add 未指定的字段填充默认值。"""
    ref = ref or datetime.now().astimezone()
    out = dict(fields)

    if not out.get("owner"):
        out["owner"] = get_default_owner_name()

    if not out.get("due_at"):
        out["due_at"] = default_due_datetime(ref).isoformat()

    due_dt = datetime.fromisoformat(out["due_at"])
    if due_dt.tzinfo is None:
        due_dt = due_dt.astimezone()

    if out.pop("_remind_absolute", False):
        schedule = list(out.get("remind_schedule") or [])
        if not schedule and out.get("remind_at"):
            schedule = [out["remind_at"]]
        out["remind_schedule"] = schedule
        out["remind_at"] = next_remind_from_schedule(schedule, ref=ref) or out.get("remind_at")
    elif not out.get("remind_spec"):
        out["remind_spec"] = DEFAULT_REMIND_SPEC
        schedule = build_remind_schedule(due_dt, DEFAULT_REMIND_SPEC, ref=ref)
        out["remind_schedule"] = schedule
        out["remind_at"] = schedule[0] if schedule else None
    elif not out.get("remind_at"):
        schedule = build_remind_schedule(due_dt, out["remind_spec"], ref=ref)
        out["remind_schedule"] = schedule
        out["remind_at"] = schedule[0] if schedule else None

    if not out.get("repeat_rule"):
        out["repeat_rule"] = None
        out["repeat_end"] = None

    return out
