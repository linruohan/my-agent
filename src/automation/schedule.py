"""定时任务调度表达式解析。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.astimezone()
    return dt.astimezone()


def compute_next_run(schedule: dict, after: datetime | None = None) -> datetime | None:
    """根据 schedule 计算下次运行时间。

    支持：
    - interval: {"type": "interval", "minutes": 60}
    - daily: {"type": "daily", "hour": 9, "minute": 0}
    - cron: {"type": "cron", "expr": "0 9 * * *"}
    """
    if not schedule:
        return None
    now = _aware(after or datetime.now().astimezone())
    kind = str(schedule.get("type", "")).lower()

    if kind == "interval":
        minutes = int(schedule.get("minutes") or schedule.get("interval_minutes") or 60)
        minutes = max(1, minutes)
        return now + timedelta(minutes=minutes)

    if kind == "daily":
        hour = int(schedule.get("hour", 9))
        minute = int(schedule.get("minute", 0))
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    if kind == "cron":
        expr = str(schedule.get("expr", "")).strip()
        if not expr:
            return None
        try:
            from croniter import croniter

            base = now.replace(second=0, microsecond=0)
            itr = croniter(expr, base)
            nxt = itr.get_next(datetime)
            return _aware(nxt)
        except Exception:
            return None

    return None


def format_schedule(schedule: dict) -> str:
    kind = str(schedule.get("type", "")).lower()
    if kind == "interval":
        return f"每 {schedule.get('minutes', 60)} 分钟"
    if kind == "daily":
        return f"每天 {int(schedule.get('hour', 9)):02d}:{int(schedule.get('minute', 0)):02d}"
    if kind == "cron":
        return f"cron: {schedule.get('expr', '')}"
    return str(schedule)
