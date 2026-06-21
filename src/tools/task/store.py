"""任务 SQLite 存储（task.db）与到期提醒。"""

from __future__ import annotations

import html
import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from src.infra.paths import DATA_DIR
from src.infra.sqlite_store import ReusableSqliteStore
from src.tools.task.attachments import apply_content_attachments, merge_attachments
from src.tools.task.parse import parse_task_add_with_defaults, parse_task_edit

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    content     TEXT NOT NULL DEFAULT '',
    due_at      TEXT,
    repeat_rule TEXT,
    remind_at   TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    status      TEXT NOT NULL DEFAULT 'pending',
    owner       TEXT,
    repeat_end  TEXT,
    repeat_count INTEGER NOT NULL DEFAULT 0,
    remind_spec TEXT,
    remind_schedule TEXT,
    attachments TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_at);
"""

VALID_STATUS = {"pending", "done", "expired", "planned"}


def _load_remind_schedule(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [str(x) for x in data]
    return []


def _load_attachments(raw: str | None) -> list[dict[str, str]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        val = str(item.get("value") or "").strip()
        if not val:
            continue
        kind = str(item.get("type") or "file").lower()
        out.append({"type": "url" if kind == "url" else "file", "value": val})
    return out


@dataclass
class TaskRow:
    id: int
    title: str
    content: str
    due_at: str | None
    repeat_rule: str | None
    remind_at: str | None
    created_at: str
    updated_at: str
    tags: list[str] = field(default_factory=list)
    status: str = "pending"
    owner: str | None = None
    repeat_end: str | None = None
    repeat_count: int = 0
    remind_spec: str | None = None
    remind_schedule: list[str] = field(default_factory=list)
    attachments: list[dict[str, str]] = field(default_factory=list)


class TaskStore(ReusableSqliteStore):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(db_path or (DATA_DIR / "task.db"))
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            self._migrate_columns(conn)

    @staticmethod
    def _migrate_columns(conn: sqlite3.Connection) -> None:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner TEXT")
        if "repeat_end" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN repeat_end TEXT")
        if "repeat_count" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN repeat_count INTEGER NOT NULL DEFAULT 0")
        if "remind_spec" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN remind_spec TEXT")
        if "remind_schedule" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN remind_schedule TEXT")
        if "attachments" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN attachments TEXT NOT NULL DEFAULT '[]'")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _row_from_db(row: sqlite3.Row) -> TaskRow:
        tags_raw = row["tags"] or "[]"
        try:
            tags = json.loads(tags_raw)
        except json.JSONDecodeError:
            tags = []
        return TaskRow(
            id=int(row["id"]),
            title=row["title"],
            content=row["content"] or "",
            due_at=row["due_at"],
            repeat_rule=row["repeat_rule"],
            remind_at=row["remind_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            tags=[str(t) for t in tags],
            status=row["status"] or "pending",
            owner=row["owner"],
            repeat_end=row["repeat_end"],
            repeat_count=int(row["repeat_count"] or 0),
            remind_spec=row["remind_spec"],
            remind_schedule=_load_remind_schedule(row["remind_schedule"]),
            attachments=_load_attachments(row["attachments"]),
        )

    def add(
        self,
        title: str,
        content: str = "",
        *,
        due_at: str | None = None,
        repeat_rule: str | None = None,
        remind_at: str | None = None,
        tags: list[str] | None = None,
        status: str = "pending",
        created_at: str | None = None,
        owner: str | None = None,
        repeat_end: str | None = None,
        remind_spec: str | None = None,
        remind_schedule: list[str] | None = None,
        attachments: list[dict[str, str]] | None = None,
        repeat_count: int = 0,
    ) -> TaskRow:
        title = (title or "").strip()
        if not title:
            raise ValueError("任务名不能为空")
        status = status if status in VALID_STATUS else "pending"
        now = created_at or self._now()
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        if remind_at is None and remind_spec and due_at and not remind_schedule:
            try:
                due_dt = self._parse_iso(due_at)
                from src.tools.task.defaults import build_remind_schedule

                remind_schedule = build_remind_schedule(due_dt, remind_spec)
                remind_at = remind_schedule[0] if remind_schedule else None
            except ValueError:
                pass
        schedule_json = json.dumps(remind_schedule or [], ensure_ascii=False)
        attachments_json = json.dumps(attachments or [], ensure_ascii=False)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO tasks
                    (title, content, due_at, repeat_rule, remind_at, created_at, updated_at,
                     tags, status, owner, repeat_end, repeat_count, remind_spec, remind_schedule, attachments)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title, content or "", due_at, repeat_rule, remind_at, now, now,
                    tags_json, status, owner, repeat_end, repeat_count, remind_spec,
                    schedule_json, attachments_json,
                ),
            )
            tid = int(cur.lastrowid)
        row = self.get(tid)
        assert row is not None
        return row

    def get(self, task_id: int) -> TaskRow | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_from_db(row) if row else None

    def list_incomplete(self) -> list[TaskRow]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status IN ('pending', 'planned', 'expired')
                ORDER BY id DESC
                """
            ).fetchall()
        return [self._row_from_db(r) for r in rows]

    def list_all(self, *, include_done: bool = False) -> list[TaskRow]:
        with self._connect() as conn:
            if include_done:
                rows = conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM tasks
                    WHERE status IN ('pending', 'planned', 'expired')
                    ORDER BY id DESC
                    """
                ).fetchall()
        return [self._row_from_db(r) for r in rows]

    def search(self, keyword: str) -> list[TaskRow]:
        kw = f"%{keyword.strip()}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE title LIKE ? OR content LIKE ?
                ORDER BY id DESC
                """,
                (kw, kw),
            ).fetchall()
        return [self._row_from_db(r) for r in rows]

    def delete(self, task_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cur.rowcount > 0

    def update_status(self, task_id: int, status: str) -> bool:
        if status not in VALID_STATUS:
            return False
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status, self._now(), task_id),
            )
            return cur.rowcount > 0

    def update(
        self,
        task_id: int,
        *,
        title: str | None = None,
        content: str | None = None,
        due_at: str | None = None,
        repeat_rule: str | None = None,
        remind_at: str | None = None,
        tags: list[str] | None = None,
        status: str | None = None,
        owner: str | None = None,
        repeat_end: str | None = None,
        repeat_count: int | None = None,
        remind_spec: str | None = None,
        remind_schedule: list[str] | None = None,
        attachments: list[dict[str, str]] | None = None,
        clear_remind: bool = False,
        clear_remind_spec: bool = False,
    ) -> bool:
        row = self.get(task_id)
        if not row:
            return False
        fields: dict[str, Any] = {}
        if title is not None:
            title = title.strip()
            if not title:
                raise ValueError("任务名不能为空")
            fields["title"] = title
        if content is not None:
            fields["content"] = content
        if due_at is not None:
            fields["due_at"] = due_at
        if repeat_rule is not None:
            fields["repeat_rule"] = repeat_rule
        if clear_remind:
            fields["remind_at"] = None
            fields["remind_schedule"] = json.dumps([], ensure_ascii=False)
        elif remind_at is not None:
            fields["remind_at"] = remind_at
        if remind_schedule is not None:
            fields["remind_schedule"] = json.dumps(remind_schedule, ensure_ascii=False)
        if tags is not None:
            fields["tags"] = json.dumps(tags, ensure_ascii=False)
        if status is not None:
            if status not in VALID_STATUS:
                raise ValueError(f"无效状态：{status}")
            fields["status"] = status
        if owner is not None:
            fields["owner"] = owner
        if repeat_end is not None:
            fields["repeat_end"] = repeat_end
        if repeat_count is not None:
            fields["repeat_count"] = repeat_count
        if clear_remind_spec:
            fields["remind_spec"] = None
        elif remind_spec is not None:
            fields["remind_spec"] = remind_spec
        if attachments is not None:
            fields["attachments"] = json.dumps(attachments, ensure_ascii=False)
        if not fields:
            return True
        fields["updated_at"] = self._now()
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [task_id]
        with self._connect() as conn:
            cur = conn.execute(f"UPDATE tasks SET {sets} WHERE id = ?", vals)
            return cur.rowcount > 0

    @staticmethod
    def _parse_iso(value: str) -> datetime:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.astimezone()
        return dt

    def due_for_reminder(self, now: datetime | None = None) -> list[TaskRow]:
        now = now or datetime.now().astimezone()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status IN ('pending', 'planned')
                  AND remind_at IS NOT NULL
                """
            ).fetchall()
        due_rows: list[TaskRow] = []
        for r in rows:
            row = self._row_from_db(r)
            if not row.remind_at:
                continue
            try:
                if self._parse_iso(row.remind_at) <= now:
                    due_rows.append(row)
            except ValueError:
                continue
        return sorted(due_rows, key=lambda x: x.remind_at or "")

    def due_for_due(self, now: datetime | None = None) -> list[TaskRow]:
        now = now or datetime.now().astimezone()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status IN ('pending', 'planned')
                  AND due_at IS NOT NULL
                """
            ).fetchall()
        due_rows: list[TaskRow] = []
        for r in rows:
            row = self._row_from_db(r)
            if not row.due_at:
                continue
            try:
                if self._parse_iso(row.due_at) <= now:
                    due_rows.append(row)
            except ValueError:
                continue
        return sorted(due_rows, key=lambda x: x.due_at or "")

    def mark_reminded(self, task_id: int) -> None:
        row = self.get(task_id)
        if not row:
            return
        fired = row.remind_at
        schedule = list(row.remind_schedule or [])
        if fired and fired in schedule:
            schedule = [s for s in schedule if s != fired]
        elif schedule:
            schedule = schedule[1:]
        next_at = min(schedule) if schedule else None
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tasks SET remind_at = ?, remind_schedule = ?, updated_at = ? WHERE id = ?
                """,
                (next_at, json.dumps(schedule, ensure_ascii=False), self._now(), task_id),
            )


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


_LEGACY_TODOS = DATA_DIR / "workspace" / "todos.json"


def migrate_legacy_todos_json(store: TaskStore | None = None) -> int:
    """将旧版 workspace/todos.json 一次性导入 task.db，成功后重命名为 .migrated。"""
    if not _LEGACY_TODOS.is_file():
        return 0
    store = store or TaskStore()
    try:
        raw = json.loads(_LEGACY_TODOS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("读取 legacy todos.json 失败: {}", exc)
        return 0
    if not isinstance(raw, list):
        return 0

    imported = 0
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        priority = str(item.get("priority") or "normal")
        tags = [priority] if priority and priority != "normal" else []
        status = "done" if item.get("done") else "pending"
        due_date = item.get("due_date")
        due_at = f"{due_date}T00:00:00" if due_date else None
        created_at = item.get("created_at")
        if isinstance(created_at, str) and created_at and not created_at.endswith("Z"):
            if "+" not in created_at and "T" in created_at:
                created_at = f"{created_at}Z"
        try:
            store.add(
                title,
                "",
                due_at=due_at,
                tags=tags or None,
                status=status,
                created_at=str(created_at) if created_at else None,
            )
            imported += 1
        except ValueError:
            continue

    if imported >= 0:
        backup = _LEGACY_TODOS.with_suffix(".json.migrated")
        try:
            _LEGACY_TODOS.replace(backup)
            if imported:
                logger.info("已迁移 {} 条 legacy 待办至 task.db，备份为 {}", imported, backup.name)
        except OSError as exc:
            logger.warning("迁移完成但无法重命名 todos.json: {}", exc)
    return imported


# 兼容旧导入
def send_windows_toast(title: str, message: str) -> bool:
    from src.tools.task.notify import send_task_toast

    return send_task_toast(title, message)
