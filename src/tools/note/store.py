"""笔记 SQLite 存储（note.db）。"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.infra.paths import DATA_DIR
from src.infra.sqlite_store import ReusableSqliteStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_title ON notes(title);
"""


@dataclass
class NoteRow:
    id: int
    title: str
    content: str
    created_at: str
    updated_at: str


class NoteStore(ReusableSqliteStore):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(db_path or (DATA_DIR / "note.db"))
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def add(self, title: str, content: str) -> NoteRow:
        title = (title or "").strip() or (content or "").strip()[:30] or "无标题"
        content = (content or "").strip()
        if not content:
            raise ValueError("笔记内容不能为空")
        now = self._now()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO notes (title, content, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (title, content, now, now),
            )
            nid = int(cur.lastrowid)
        return NoteRow(id=nid, title=title, content=content, created_at=now, updated_at=now)

    def list_all(self) -> list[NoteRow]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, title, content, created_at, updated_at FROM notes ORDER BY id DESC"
            ).fetchall()
        return [NoteRow(**dict(r)) for r in rows]

    def search(self, keyword: str) -> list[NoteRow]:
        kw = f"%{keyword.strip()}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, title, content, created_at, updated_at FROM notes
                WHERE title LIKE ? OR content LIKE ?
                ORDER BY id DESC
                """,
                (kw, kw),
            ).fetchall()
        return [NoteRow(**dict(r)) for r in rows]

    def get(self, note_id: int) -> NoteRow | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, title, content, created_at, updated_at FROM notes WHERE id = ?",
                (note_id,),
            ).fetchone()
        return NoteRow(**dict(row)) if row else None

    def delete(self, note_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            return cur.rowcount > 0


def _format_created_at(iso: str) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso[:16].replace("T", " ")


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


def format_note_list(rows: list[NoteRow]) -> str:
    if not rows:
        return "暂无笔记。"
    lines = ["| ID | 标题 |", "| --- | --- |"]
    for r in rows:
        title = r.title.replace("|", "\\|")
        lines.append(f"| {r.id} | {title} |")
    return "笔记列表：\n\n" + "\n".join(lines)


def format_note_search(rows: list[NoteRow], keyword: str) -> str:
    if not rows:
        return f"未找到与「{keyword}」相关的笔记。"
    lines = ["| ID | 标题 | 内容 | 创建时间 |", "| --- | --- | --- | --- |"]
    for r in rows:
        preview = r.content.replace("\n", " ")[:120]
        created = _format_created_at(r.created_at)
        lines.append(
            f"| {r.id} | {_hl(r.title, keyword)} | {_hl(preview, keyword)} | {created} |"
        )
    return f"笔记搜索「{keyword}」：\n\n" + "\n".join(lines)


def handle_note_command(args: str, store: NoteStore | None = None) -> str:
    store = store or NoteStore()
    body = (args or "").strip()
    if not body:
        return "用法：/note add <标题> <内容> | list | <关键字> | rm <id>"

    parts = body.split(None, 2)
    sub = parts[0].lower()

    if sub == "list":
        return format_note_list(store.list_all())

    if sub == "add":
        if len(parts) < 3:
            return "用法：/note add <标题> <内容>"
        title, content = parts[1], parts[2]
        row = store.add(title, content)
        return f"已添加笔记 #{row.id}：{row.title}"

    if sub == "rm":
        if len(parts) < 2 or not parts[1].isdigit():
            return "用法：/note rm <笔记ID>"
        nid = int(parts[1])
        if store.delete(nid):
            return f"已删除笔记 #{nid}"
        return f"未找到笔记 #{nid}"

    if sub.isdigit():
        row = store.get(int(sub))
        if not row:
            return f"未找到笔记 #{sub}"
        created = _format_created_at(row.created_at)
        return f"#{row.id} {row.title}（创建：{created}）\n\n{row.content}"

    keyword = body
    return format_note_search(store.search(keyword), keyword)
