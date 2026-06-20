from __future__ import annotations

import json

from src.tools import create_todo, list_todos, read_calendar, web_search


def test_web_search_returns_text():
    result = web_search.invoke({"query": "Python"})
    assert "Python" in result


def test_todo_lifecycle(tmp_path, monkeypatch):
    import src.tools as tools_mod

    todo_file = tmp_path / "todos.json"
    monkeypatch.setattr(tools_mod, "_TODOS_FILE", todo_file)

    create_todo.invoke({"title": "测试任务", "priority": "high"})
    result = list_todos.invoke({"include_done": False})
    assert "测试任务" in result
    assert todo_file.exists()


def test_read_calendar_empty(tmp_path, monkeypatch):
    import src.tools as tools_mod

    cal_file = tmp_path / "calendar.json"
    cal_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(tools_mod, "_CALENDAR_FILE", cal_file)

    result = read_calendar.invoke({"date": "2026-06-20"})
    assert "暂无日程" in result
