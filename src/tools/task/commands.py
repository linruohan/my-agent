"""任务列表格式化与 /tsk 斜杠命令。"""

from __future__ import annotations

import html
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.tools.task.attachments import apply_content_attachments, merge_attachments
from src.tools.task.parse import parse_task_add_with_defaults, parse_task_edit
from src.tools.task.store import TaskRow, TaskStore


def _hl(text: str, keyword: str) -> str:
    if not keyword:
        return html.escape(text)
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    result: list[str] = []
    last = 0
    for m in pattern.finditer(text):
        result.append(html.escape(text[last : m.start()]))
        result.append(f'<mark class="kw-hl">{html.escape(m.group(0))}</mark>')
        last = m.end()
    result.append(html.escape(text[last:]))
    return "".join(result)


def _escape_cell(text: str) -> str:
    return (text or "—").replace("|", "\\|").replace("\n", " ")


def _fmt_dt_short(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.astimezone()
        else:
            dt = dt.astimezone()
        today = datetime.now().astimezone().date()
        if dt.date() == today:
            return dt.strftime("今天 %H:%M")
        if dt.date() == today + timedelta(days=1):
            return dt.strftime("明天 %H:%M")
        return dt.strftime("%m/%d %H:%M")
    except ValueError:
        return iso[:16]


def _fmt_repeat(rule: str | None) -> str:
    if not rule:
        return "—"
    from src.tools.task.repeat import decode_repeat_rule

    parsed = decode_repeat_rule(rule)
    if not parsed:
        return _escape_cell(rule[:24])
    unit_map = {"day": "天", "week": "周", "month": "月", "year": "年"}
    unit = unit_map.get(parsed["unit"], parsed["unit"])
    return f"{parsed['every']}{unit}×{parsed['times']}"


def _fmt_remind(row: TaskRow) -> str:
    if row.remind_schedule:
        n = len(row.remind_schedule)
        nxt = _fmt_dt_short(row.remind_at)
        return f"{n}次({nxt})" if nxt != "—" else f"{n}次"
    return _fmt_dt_short(row.remind_at)


def _fmt_tags(tags: list[str]) -> str:
    if not tags:
        return "—"
    text = ",".join(tags)
    return text if len(text) <= 16 else text[:15] + "…"


def _fmt_attachments(row: TaskRow) -> str:
    if not row.attachments:
        return "—"
    lines: list[str] = []
    for att in row.attachments:
        val = (att.get("value") or "").strip()
        if not val:
            continue
        if att.get("type") == "url":
            safe = html.escape(val, quote=True)
            label = html.escape(val)
            lines.append(f'<a href="{safe}" target="_blank" rel="noopener noreferrer">{label}</a>')
        else:
            lines.append(html.escape(val))
    return "<br>".join(lines) if lines else "—"


def _finalize_task_text(title: str, content: str) -> tuple[str, str, list[dict[str, str]]]:
    t, c, attachments = apply_content_attachments(title or "", content or "")
    if not (t or "").strip():
        for att in attachments:
            if att.get("type") == "file":
                t = Path(att["value"]).name
                break
        if not (t or "").strip() and attachments:
            t = attachments[0]["value"]
    return (t or "").strip(), (c or "").strip(), attachments


def _task_table_row(r: TaskRow) -> str:
    title = r.title if len(r.title) <= 20 else r.title[:19] + "…"
    return (
        f"| {r.id} | {_escape_cell(title)} | {_escape_cell(r.owner or '—')} "
        f"| {_fmt_dt_short(r.due_at)} | {_fmt_remind(r)} | {_fmt_repeat(r.repeat_rule)} "
        f"| {_fmt_tags(r.tags)} | {_fmt_attachments(r)} | {r.status} |"
    )


def format_task_list(rows: list[TaskRow], *, heading: str = "未完成任务：") -> str:
    if not rows:
        return "暂无未完成任务。" if heading.startswith("未完成") else "当前没有任务。"
    header = "| ID | 标题 | 负责人 | 截止 | 提醒 | 重复 | 标签 | 附件 | 状态 |"
    sep = "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    lines = [header, sep, *(_task_table_row(r) for r in rows)]
    return f"{heading}\n\n" + "\n".join(lines)


def format_task_search(rows: list[TaskRow], keyword: str) -> str:
    if not rows:
        return f"未找到与「{keyword}」相关的任务。"
    lines = ["| ID | 标题 | 内容 |", "| --- | --- | --- |"]
    for r in rows:
        preview = r.content.replace("\n", " ")[:120]
        lines.append(f"| {r.id} | {_hl(r.title, keyword)} | {_hl(preview, keyword)} |")
    return f"任务搜索「{keyword}」：\n\n" + "\n".join(lines)


def _format_task_detail(row: TaskRow) -> str:
    remind_text = row.remind_at or "—"
    if row.remind_schedule:
        remind_text = ", ".join(row.remind_schedule)
    att_lines = []
    for att in row.attachments:
        val = att.get("value") or ""
        if att.get("type") == "url":
            att_lines.append(f"- 🔗 {val}")
        else:
            att_lines.append(f"- 📎 {val}")
    att_block = "\n".join(att_lines) if att_lines else "—"
    return (
        f"#{row.id} {row.title} [{row.status}]\n"
        f"负责人：{row.owner or '—'}  到期：{row.due_at or '—'}  提醒：{remind_text}\n"
        f"重复：{row.repeat_rule or '—'}  结束：{row.repeat_end or '—'}  已执行：{row.repeat_count}\n"
        f"标签：{', '.join(row.tags) or '—'}\n"
        f"附件：\n{att_block}\n\n{row.content}"
    )


def _apply_task_edit(store: TaskStore, task_id: int, parsed) -> TaskRow:
    row = store.get(task_id)
    if not row:
        raise ValueError(f"未找到任务 #{task_id}")

    kwargs: dict[str, Any] = {}
    if parsed.title is not None:
        kwargs["title"] = parsed.title
    if parsed.content is not None:
        kwargs["content"] = parsed.content
    if parsed.owner_set:
        kwargs["owner"] = parsed.owner
    if parsed.tags_set:
        kwargs["tags"] = parsed.tags or []
    if parsed.due_set:
        kwargs["due_at"] = parsed.due_at
    if parsed.repeat_set:
        kwargs["repeat_rule"] = parsed.repeat_rule
    if parsed.repeat_end_set:
        kwargs["repeat_end"] = parsed.repeat_end
    if parsed.remind_set:
        due_iso = parsed.due_at or row.due_at
        if parsed.remind_absolute and parsed.remind_at:
            from src.tools.task.defaults import append_remind_to_schedule

            schedule, next_at = append_remind_to_schedule(row.remind_schedule, parsed.remind_at)
            kwargs["remind_schedule"] = schedule
            kwargs["remind_at"] = next_at
        elif parsed.remind_at:
            kwargs["remind_at"] = parsed.remind_at
        elif parsed.remind_spec and due_iso:
            due_dt = datetime.fromisoformat(due_iso)
            from src.tools.task.defaults import build_remind_schedule

            schedule = build_remind_schedule(due_dt, parsed.remind_spec)
            kwargs["remind_schedule"] = schedule
            kwargs["remind_at"] = schedule[0] if schedule else None
        if parsed.remind_spec and not parsed.remind_absolute:
            kwargs["remind_spec"] = parsed.remind_spec

    if parsed.title is not None or parsed.content is not None:
        final_title = kwargs.get("title", row.title)
        final_content = kwargs.get("content", row.content)
        ft, fc, extracted = _finalize_task_text(final_title, final_content)
        if not ft:
            raise ValueError("任务名不能为空")
        kwargs["title"] = ft
        kwargs["content"] = fc
        kwargs["attachments"] = merge_attachments(row.attachments, extracted)

    if not kwargs:
        raise ValueError("未指定要修改的字段")

    store.update(task_id, **kwargs)
    updated = store.get(task_id)
    assert updated is not None
    return updated


def handle_task_command(args: str, store: TaskStore | None = None) -> str:
    store = store or TaskStore()
    body = (args or "").strip()
    if not body:
        return (
            "用法：/tsk add <任务名> [内容] [标记…] | mod <任务ID> <修改内容> | list | notify [id] | tick | rm <id> | <id> | <关键字>\n"
            "标记：@{owner} #{tag} @due-日期 @rem-1m|1h|1d|具体时间 @rep-1day-2|@rep-day @rep-end-none|日期|次数\n"
            "mod 时 @rem-6.22.10:00 等具体时间会在现有提醒计划中追加一条\n"
            "add 未指定时默认：负责人=设置中的名字，截止=当天17:30，"
            "提醒=截止前一天9:00/14:30/16:30，无@rep-则不重复"
        )

    parts = body.split(None, 1)
    sub = parts[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""

    if sub == "list":
        return format_task_list(store.list_incomplete())

    if sub == "notify":
        from src.tools.task.notify import send_task_toast

        tid_s = rest.split(None, 1)[0] if rest else ""
        if tid_s.isdigit():
            row = store.get(int(tid_s))
            if not row:
                return f"未找到任务 #{tid_s}"
            msg = row.content[:200] if row.content else ""
            ok = send_task_toast(
                row.title,
                msg,
                owner=row.owner,
                due_at=row.due_at,
                kind="reminder",
            )
            return f"已发送提醒 #{row.id}（{'成功' if ok else '失败，请检查系统通知权限'}）"
        demo_due = (datetime.now().astimezone() + timedelta(hours=2)).isoformat()
        ok = send_task_toast(
            "示例任务",
            "这是一条测试通知",
            owner="林若寒",
            due_at=demo_due,
            kind="reminder",
        )
        return f"测试通知已发送（{'成功' if ok else '失败，请检查系统通知权限'}）"

    if sub == "tick":
        from src.tools.task.scheduler import TaskReminderService

        now = datetime.now().astimezone()
        due_rem = store.due_for_reminder(now)
        due_tasks = store.due_for_due(now)
        ids_rem = [r.id for r in due_rem]
        ids_due = [r.id for r in due_tasks]
        TaskReminderService(store).tick(now)
        parts: list[str] = []
        if ids_rem:
            parts.append(f"已处理提醒 {', '.join(f'#{i}' for i in ids_rem)}")
        else:
            parts.append("当前无到期提醒")
        if ids_due:
            parts.append(f"已处理到期 {', '.join(f'#{i}' for i in ids_due)}")
        return "；".join(parts)

    if sub == "mod":
        if not rest:
            return "用法：/tsk mod <任务ID> <修改内容>（必须指定任务 ID）"
        id_parts = rest.split(None, 1)
        if not id_parts[0].isdigit():
            return "用法：/tsk mod <任务ID> <修改内容>（任务 ID 须为数字）"
        tid = int(id_parts[0])
        mod_text = id_parts[1].strip() if len(id_parts) > 1 else ""
        if not mod_text:
            return f"用法：/tsk mod {tid} <要修改的字段或标题>"
        try:
            parsed = parse_task_edit(mod_text)
            row = _apply_task_edit(store, tid, parsed)
            return f"已更新任务 #{row.id}：{row.title}"
        except ValueError as exc:
            return str(exc)

    if sub == "add":
        try:
            parsed = parse_task_add_with_defaults(rest)
            title, content, attachments = _finalize_task_text(
                parsed["title"],
                parsed.get("content", ""),
            )
            if not title:
                raise ValueError("任务名不能为空")
            parsed["title"] = title
            parsed["content"] = content
            parsed["attachments"] = attachments
            row = store.add(**parsed)
            return f"已添加任务 #{row.id}：{row.title}（{row.status}）"
        except ValueError as exc:
            return str(exc)

    if sub == "rm":
        tid_s = rest.split(None, 1)[0] if rest else ""
        if not tid_s.isdigit():
            return "用法：/tsk rm <任务ID>"
        tid = int(tid_s)
        if store.delete(tid):
            return f"已删除任务 #{tid}"
        return f"未找到任务 #{tid}"

    if sub.isdigit():
        row = store.get(int(sub))
        if not row:
            return f"未找到任务 #{sub}"
        return _format_task_detail(row)

    return format_task_search(store.search(body), body)

