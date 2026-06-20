from __future__ import annotations

from unittest.mock import patch

import src.tools.task.tools as task_tools
from src.tools import add_task, list_tasks, read_calendar, web_search


def test_web_search_returns_text():
    with patch("src.tools.web.core.web_search_impl", return_value="关于 Python 的搜索结果"):
        result = web_search.invoke({"query": "Python"})
    assert "Python" in result


def test_task_lifecycle(tmp_path, monkeypatch):
    db = tmp_path / "task.db"
    store_cls = __import__("src.tools.task.store", fromlist=["TaskStore"]).TaskStore
    monkeypatch.setattr(task_tools, "TaskStore", lambda: store_cls(db))

    add_task.invoke({"title": "测试任务", "content": "高优先级", "tags": "high"})
    result = list_tasks.invoke({"include_done": False})
    assert "测试任务" in result
    assert db.exists()


def test_read_calendar_empty(tmp_path, monkeypatch):
    import src.tools.workspace.tools as workspace_tools

    cal_file = tmp_path / "calendar.json"
    cal_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(workspace_tools, "_CALENDAR_FILE", cal_file)

    result = read_calendar.invoke({"date": "2026-06-20"})
    assert "暂无日程" in result
