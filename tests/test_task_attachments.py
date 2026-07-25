"""任务附件提取测试。"""

from __future__ import annotations

from pathlib import Path

from src.tools.task.attachments import apply_content_attachments, extract_attachments
from src.tools.task.commands import handle_task_command
from src.tools.task.store import TaskStore


def test_extract_url_and_file():
    text = "详见 D:\\docs\\report.pdf 以及 https://example.com/a"
    cleaned, att = extract_attachments(text)
    assert "report.pdf" not in cleaned or cleaned == ""
    assert len(att) == 2
    types = {a["type"] for a in att}
    assert types == {"file", "url"}


def test_handle_task_add_extracts_attachments(tmp_path: Path):
    store = TaskStore(tmp_path / "task.db")
    f = tmp_path / "note.txt"
    f.write_text("hi", encoding="utf-8")
    path = str(f.resolve())
    result = handle_task_command(f"add 整理材料 {path} https://example.com", store)
    assert "已添加任务" in result
    row = store.get(1)
    assert row is not None
    assert row.title == "整理材料"
    assert row.content == ""
    assert len(row.attachments) == 2
    assert any(a["type"] == "file" and a["value"] == path for a in row.attachments)
    assert any(a["type"] == "url" for a in row.attachments)

    listed = handle_task_command("list", store)
    assert "附件" in listed
    assert "example.com" in listed
    assert path.replace("\\", "\\\\") in listed or path in listed


def test_apply_content_attachments_dedupe():
    t, c, att = apply_content_attachments(
        "标题 https://a.com",
        "https://a.com D:\\work\\a.docx",
    )
    assert t == "标题"
    assert "https://a.com" not in c
    assert len(att) == 2
