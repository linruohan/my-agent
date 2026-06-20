"""任务 SQLite 存储（task.db）与到期提醒。"""

from __future__ import annotations

import html
import json
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from loguru import logger

from src.infra.paths import DATA_DIR

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
    status      TEXT NOT NULL DEFAULT 'pending'
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_at);
"""

VALID_STATUS = {"pending", "done", "expired", "planned"}


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


class TaskStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (DATA_DIR / "task.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

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
    ) -> TaskRow:
        title = (title or "").strip()
        if not title:
            raise ValueError("任务名不能为空")
        status = status if status in VALID_STATUS else "pending"
        now = created_at or self._now()
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO tasks
                    (title, content, due_at, repeat_rule, remind_at, created_at, updated_at, tags, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (title, content or "", due_at, repeat_rule, remind_at, now, now, tags_json, status),
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

    def due_for_reminder(self, now: datetime | None = None) -> list[TaskRow]:
        now = now or datetime.now(timezone.utc)
        now_iso = now.isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status IN ('pending', 'planned')
                  AND remind_at IS NOT NULL AND remind_at <= ?
                ORDER BY remind_at ASC
                """,
                (now_iso,),
            ).fetchall()
        return [self._row_from_db(r) for r in rows]

    def mark_reminded(self, task_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET remind_at = NULL, updated_at = ? WHERE id = ?",
                (self._now(), task_id),
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


def format_task_list(rows: list[TaskRow]) -> str:
    if not rows:
        return "暂无未完成任务。"
    lines = ["| ID | 标题 | 状态 |", "| --- | --- | --- |"]
    for r in rows:
        title = r.title.replace("|", "\\|")
        lines.append(f"| {r.id} | {title} | {r.status} |")
    return "未完成任务：\n\n" + "\n".join(lines)


def format_task_search(rows: list[TaskRow], keyword: str) -> str:
    if not rows:
        return f"未找到与「{keyword}」相关的任务。"
    lines = ["| ID | 标题 | 内容 |", "| --- | --- | --- |"]
    for r in rows:
        preview = r.content.replace("\n", " ")[:120]
        lines.append(f"| {r.id} | {_hl(r.title, keyword)} | {_hl(preview, keyword)} |")
    return f"任务搜索「{keyword}」：\n\n" + "\n".join(lines)


def _parse_add_args(rest: str) -> dict[str, Any]:
    """解析 add 参数：任务名 内容 [due=] [repeat=] [remind=] [tags=] [status=]"""
    tokens = rest.split()
    if len(tokens) < 2:
        raise ValueError("用法：/tsk add <任务名> <内容> [due=日期] [repeat=规则] [remind=时间] [tags=a,b] [status=pending]")
    title = tokens[0]
    meta: dict[str, str] = {}
    body_tokens: list[str] = []
    for tok in tokens[1:]:
        if "=" in tok and tok.split("=", 1)[0] in ("due", "repeat", "remind", "tags", "status"):
            k, v = tok.split("=", 1)
            meta[k] = v
        else:
            body_tokens.append(tok)
    content = " ".join(body_tokens)
    tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
    return {
        "title": title,
        "content": content,
        "due_at": meta.get("due") or None,
        "repeat_rule": meta.get("repeat") or None,
        "remind_at": meta.get("remind") or None,
        "tags": tags,
        "status": meta.get("status") or "pending",
    }


def handle_task_command(args: str, store: TaskStore | None = None) -> str:
    store = store or TaskStore()
    body = (args or "").strip()
    if not body:
        return "用法：/tsk add ... | list | <关键字> | rm <id>"

    parts = body.split(None, 1)
    sub = parts[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""

    if sub == "list":
        return format_task_list(store.list_incomplete())

    if sub == "add":
        try:
            parsed = _parse_add_args(rest)
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
        return (
            f"#{row.id} {row.title} [{row.status}]\n"
            f"到期：{row.due_at or '—'}  提醒：{row.remind_at or '—'}  重复：{row.repeat_rule or '—'}\n"
            f"标签：{', '.join(row.tags) or '—'}\n\n{row.content}"
        )

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


def send_windows_toast(title: str, message: str) -> bool:
    import sys

    if sys.platform != "win32":
        return False
    try:
        import subprocess

        safe_title = title.replace("'", "''")
        safe_msg = message.replace("'", "''")
        ps = (
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
            "ContentType = WindowsRuntime] | Out-Null; "
            "$t = @'"
            f"<toast><visual><binding template='ToastText02'>"
            f"<text id='1'>{safe_title}</text><text id='2'>{safe_msg}</text>"
            f"</binding></visual></toast>"
            "'@; "
            "$x = New-Object Windows.Data.Xml.Dom.XmlDocument; $x.LoadXml($t); "
            "$n = [Windows.UI.Notifications.ToastNotification]::new($x); "
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('my-agent').Show($n)"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            check=False,
            capture_output=True,
            timeout=8,
        )
        return True
    except Exception as exc:
        logger.warning("Windows 通知发送失败: {}", exc)
        return False


class TaskReminderService:
    """后台轮询任务提醒。"""

    def __init__(self, store: TaskStore | None = None, interval_sec: float = 60.0) -> None:
        self.store = store or TaskStore()
        self.interval_sec = interval_sec
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._notified: set[int] = set()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="task-reminder")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                for task in self.store.due_for_reminder():
                    if task.id in self._notified:
                        continue
                    msg = task.content[:200] if task.content else "任务即将到期"
                    if send_windows_toast(f"任务提醒：{task.title}", msg):
                        self._notified.add(task.id)
                        self.store.mark_reminded(task.id)
            except Exception:
                logger.exception("任务提醒轮询失败")
            self._stop.wait(self.interval_sec)
