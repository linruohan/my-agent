"""解析 /tsk add|mod 任务文本中的 @{owner} #{tag} @due- @rem- @rep- 等标记。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

_TOKEN_SPLIT = re.compile(r"[\s,，;；、]+")

_RE_OWNER = re.compile(r"^@\{([^}]+)\}$")
_RE_TAG = re.compile(r"^#\{([^}]+)\}$")
_RE_DUE = re.compile(r"^@due-(.+)$", re.IGNORECASE)
_RE_REM = re.compile(r"^@rem-(.+)$", re.IGNORECASE)
_RE_REM_OFFSET = re.compile(r"^\d+[mhd]$", re.IGNORECASE)
_RE_REP = re.compile(
    r"^@rep-(?:(\d+)(day|week|month|year)(?:-(\d+))?|(day|week|month|year)(?:-(\d+))?)$",
    re.IGNORECASE,
)
_RE_REP_END = re.compile(r"^@rep-end-(.+)$", re.IGNORECASE)
_RE_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")


@dataclass
class ParsedTaskFields:
    title: str | None = None
    content: str | None = None
    owner: str | None = None
    tags: list[str] | None = None
    due_at: str | None = None
    remind_at: str | None = None
    repeat_rule: str | None = None
    repeat_end: str | None = None
    status: str | None = None
    tags_set: bool = False
    owner_set: bool = False
    due_set: bool = False
    remind_set: bool = False
    repeat_set: bool = False
    repeat_end_set: bool = False
    remind_spec: str | None = None
    remind_absolute: bool = False


def tokenize_task_text(text: str) -> list[str]:
    return [t for t in _TOKEN_SPLIT.split((text or "").strip()) if t]


def _parse_time_hm(text: str) -> tuple[int, int]:
    m = _RE_TIME.match(text.strip())
    if not m:
        raise ValueError(f"无法解析时间：{text}")
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        raise ValueError(f"无效时间：{text}")
    return h, mi


def _with_time(dt: datetime, hour: int, minute: int) -> datetime:
    return dt.replace(hour=hour, minute=minute, second=0, microsecond=0)


def parse_due_datetime(text: str, ref: datetime | None = None) -> datetime:
    """解析 @due- 后的日期/时间文本（本地时区）。"""
    ref = ref or datetime.now().astimezone()
    raw = text.strip()
    if not raw:
        raise ValueError("截止日期不能为空")

    if raw == "明天下班前":
        base = ref + timedelta(days=1)
        return _with_time(base, 17, 30)
    if raw == "明天上班前":
        base = ref + timedelta(days=1)
        return _with_time(base, 9, 0)

    if _RE_TIME.match(raw):
        h, mi = _parse_time_hm(raw)
        return _with_time(ref, h, mi)

    if "." in raw:
        parts = raw.split(".")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            month, day = int(parts[0]), int(parts[1])
            return _with_time(ref.replace(year=ref.year, month=month, day=day), 17, 30)
        if len(parts) == 3 and ":" in parts[2]:
            month, day = int(parts[0]), int(parts[1])
            h, mi = _parse_time_hm(parts[2])
            return _with_time(ref.replace(year=ref.year, month=month, day=day), h, mi)
        if len(parts) == 4:
            y_raw, month, day, time_part = parts[0], int(parts[1]), int(parts[2]), parts[3]
            year = int(y_raw)
            if year < 100:
                year += 2000
            h, mi = _parse_time_hm(time_part)
            return _with_time(ref.replace(year=year, month=month, day=day), h, mi)

    raise ValueError(f"无法解析截止日期：{raw}")


def parse_repeat_end(text: str, ref: datetime | None = None) -> str:
    """解析 @rep-end- 值，返回 none | ISO 日期 | 数字次数。"""
    ref = ref or datetime.now().astimezone()
    raw = text.strip()
    if not raw:
        raise ValueError("重复结束条件不能为空")
    if raw.lower() == "none":
        return "none"
    if raw.isdigit():
        return raw
    dt = parse_due_datetime(raw, ref)
    return dt.isoformat()


def is_rem_offset_spec(spec: str) -> bool:
    """是否为相对截止时间的偏移规格（如 1h、1d）。"""
    return bool(_RE_REM_OFFSET.match((spec or "").strip()))


def parse_remind_datetime(text: str, ref: datetime | None = None) -> datetime:
    """解析 @rem- 后的具体日期/时间（与 @due- 格式相同）。"""
    return parse_due_datetime(text, ref)


def calc_remind_at(due: datetime, spec: str) -> datetime:
    """根据 @rem- 规格与截止时间计算提醒时间。"""
    m = re.match(r"^(\d+)([mhd])$", spec.strip().lower())
    if not m:
        raise ValueError(f"无法解析提醒时间：{spec}")
    qty, unit = int(m.group(1)), m.group(2)
    if unit == "m":
        return due - timedelta(minutes=qty)
    if unit == "h":
        return due - timedelta(hours=qty)
    if unit == "d":
        target = due.date() - timedelta(days=qty)
        return datetime(target.year, target.month, target.day, 9, 0, tzinfo=due.tzinfo)
    raise ValueError(f"无法解析提醒时间：{spec}")


def _encode_repeat(interval: int, unit: str, times: int) -> str:
    payload = {"every": interval, "unit": unit.lower(), "times": times}
    return json.dumps(payload, ensure_ascii=False)


def _classify_token(tok: str) -> tuple[str, Any] | None:
    m = _RE_OWNER.match(tok)
    if m:
        return ("owner", m.group(1).strip())
    m = _RE_TAG.match(tok)
    if m:
        return ("tag", m.group(1).strip())
    m = _RE_DUE.match(tok)
    if m:
        return ("due", m.group(1).strip())
    m = _RE_REM.match(tok)
    if m:
        return ("rem", m.group(1).lower())
    m = _RE_REP.match(tok)
    if m:
        if m.group(1) is not None:
            interval = int(m.group(1))
            unit = m.group(2).lower()
            times = int(m.group(3)) if m.group(3) else 1
        else:
            unit = m.group(4).lower()
            interval = 1
            times = int(m.group(5)) if m.group(5) else 1
        return ("rep", (interval, unit, times))
    m = _RE_REP_END.match(tok)
    if m:
        return ("rep_end", m.group(1).strip())
    return None


def parse_task_text(
    text: str,
    *,
    ref: datetime | None = None,
    for_edit: bool = False,
) -> ParsedTaskFields:
    """解析 add/edit 任务文本，提取特殊标记与标题/内容。"""
    ref = ref or datetime.now().astimezone()
    tokens = tokenize_task_text(text)
    if not tokens and not for_edit:
        raise ValueError("任务内容不能为空")

    plain: list[str] = []
    owners: list[str] = []
    tags: list[str] = []
    due_raw: str | None = None
    rem_spec: str | None = None
    rep_spec: tuple[int, str, int] | None = None
    rep_end_raw: str | None = None

    for tok in tokens:
        kind = _classify_token(tok)
        if kind is None:
            plain.append(tok)
            continue
        key, val = kind
        if key == "owner":
            owners.append(val)
        elif key == "tag":
            tags.append(val)
        elif key == "due":
            due_raw = val
        elif key == "rem":
            rem_spec = val
        elif key == "rep":
            rep_spec = val
        elif key == "rep_end":
            rep_end_raw = val

    result = ParsedTaskFields()
    if plain:
        result.title = plain[0]
        if len(plain) > 1:
            result.content = " ".join(plain[1:])
        elif not for_edit:
            result.content = ""
    elif not for_edit:
        raise ValueError("请提供任务标题（特殊标记之外需有任务名称文本）")

    if owners:
        result.owner = owners[-1]
        result.owner_set = True
    if tags:
        result.tags = tags
        result.tags_set = True

    due_dt: datetime | None = None
    if due_raw is not None:
        due_dt = parse_due_datetime(due_raw, ref)
        result.due_at = due_dt.isoformat()
        result.due_set = True

    if rem_spec is not None:
        if is_rem_offset_spec(rem_spec):
            result.remind_spec = rem_spec
            if due_dt is not None:
                result.remind_at = calc_remind_at(due_dt, rem_spec).isoformat()
                result.remind_set = True
            elif for_edit:
                result.remind_set = True
            else:
                raise ValueError("设置 @rem- 前需指定 @due- 截止时间")
        else:
            abs_dt = parse_remind_datetime(rem_spec, ref)
            result.remind_at = abs_dt.isoformat()
            result.remind_absolute = True
            result.remind_set = True

    if rep_spec is not None:
        interval, unit, times = rep_spec
        result.repeat_rule = _encode_repeat(interval, unit, times)
        result.repeat_set = True

    if rep_end_raw is not None:
        result.repeat_end = parse_repeat_end(rep_end_raw, ref)
        result.repeat_end_set = True

    return result


def parse_repeat_token(tok: str) -> tuple[int, str, int] | None:
    """解析 @rep- 标记，如 @rep-1day-2、@rep-day、@rep-day-3。"""
    kind = _classify_token(tok)
    if kind and kind[0] == "rep":
        return kind[1]
    return None


def parse_task_add(text: str, *, ref: datetime | None = None) -> dict[str, Any]:
    """解析 /tsk add 参数，返回 store.add 可用字段（未含默认值）。"""
    parsed = parse_task_text(text, ref=ref, for_edit=False)
    if not parsed.title:
        raise ValueError("任务名不能为空")
    fields: dict[str, Any] = {
        "title": parsed.title,
        "content": parsed.content or "",
        "tags": parsed.tags or [],
        "status": parsed.status or "pending",
    }
    if parsed.owner_set:
        fields["owner"] = parsed.owner
    if parsed.due_set:
        fields["due_at"] = parsed.due_at
    if parsed.remind_set:
        if parsed.remind_absolute:
            fields["remind_at"] = parsed.remind_at
            fields["remind_schedule"] = [parsed.remind_at] if parsed.remind_at else []
            fields["_remind_absolute"] = True
        else:
            fields["remind_spec"] = parsed.remind_spec
            fields["remind_at"] = parsed.remind_at
    if parsed.repeat_set:
        fields["repeat_rule"] = parsed.repeat_rule
    if parsed.repeat_end_set:
        fields["repeat_end"] = parsed.repeat_end
    return fields


def parse_task_add_with_defaults(text: str, *, ref: datetime | None = None) -> dict[str, Any]:
    """解析 /tsk add 并应用默认 owner / due / 提醒 / 重复策略。"""
    from src.tools.task.defaults import apply_add_defaults

    return apply_add_defaults(parse_task_add(text, ref=ref), ref=ref)


def parse_task_edit(text: str, *, ref: datetime | None = None) -> ParsedTaskFields:
    """解析 /tsk mod 参数，仅含特殊标记的字段会被标记为待更新。"""
    return parse_task_text(text, ref=ref, for_edit=True)
