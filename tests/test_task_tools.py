"""task 工具测试。"""

from __future__ import annotations

from pathlib import Path

import src.tools.task.tools as task_tools
from src.tools import add_task, complete_task, delete_task, list_tasks, search_tasks


def test_add_task_invokes_store(tmp_path: Path, monkeypatch):
    db = tmp_path / "task.db"
    monkeypatch.setattr(task_tools, "TaskStore", lambda: __import__("src.tools.task.store", fromlist=["TaskStore"]).TaskStore(db))

    result = add_task.invoke({"title": "写文档", "content": "完成模块化", "tags": "work"})
    assert "已添加任务 #1" in result
    assert db.exists()


def test_list_tasks_empty(tmp_path: Path, monkeypatch):
    db = tmp_path / "task.db"
    monkeypatch.setattr(task_tools, "TaskStore", lambda: __import__("src.tools.task.store", fromlist=["TaskStore"]).TaskStore(db))

    result = list_tasks.invoke({})
    assert "暂无未完成任务" in result


def test_search_tasks_keyword(tmp_path: Path, monkeypatch):
    db = tmp_path / "task.db"
    store_cls = __import__("src.tools.task.store", fromlist=["TaskStore"]).TaskStore
    store = store_cls(db)
    store.add("部署上线", "检查 CI")
    monkeypatch.setattr(task_tools, "TaskStore", lambda: store)

    result = search_tasks.invoke({"keyword": "部署"})
    assert "部署" in result
    assert "| 1 |" in result


def test_complete_and_delete_task(tmp_path: Path, monkeypatch):
    db = tmp_path / "task.db"
    store_cls = __import__("src.tools.task.store", fromlist=["TaskStore"]).TaskStore
    store = store_cls(db)
    row = store.add("临时任务", "待删除")
    monkeypatch.setattr(task_tools, "TaskStore", lambda: store)

    done = complete_task.invoke({"task_id": row.id})
    assert "已标记为完成" in done

    removed = delete_task.invoke({"task_id": row.id})
    assert "已删除任务" in removed
    assert store.get(row.id) is None
