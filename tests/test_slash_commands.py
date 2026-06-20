"""slash 命令与存储测试。"""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.memory.cache_admin import cache_display_id, handle_cache_command
from src.memory.search_cache import SearchCache
from src.memory.search_cache_db import SearchCacheStore
from src.tools.note_store import NoteStore, handle_note_command
from src.tools.task_store import TaskStore, handle_task_command
from src.ui.input_intent import INTENT_SLASH_CACHE, INTENT_SLASH_TASK, parse_slash_command


def test_parse_slash_cache():
    intent = parse_slash_command("/cache list")
    assert intent is not None
    assert intent.kind == INTENT_SLASH_CACHE
    assert intent.slash_args == "list"


def test_parse_slash_tsk():
    intent = parse_slash_command("/tsk list")
    assert intent is not None
    assert intent.kind == INTENT_SLASH_TASK


def test_note_store_crud(tmp_path: Path):
    db = tmp_path / "note.db"
    store = NoteStore(db)
    row = store.add("标题", "内容A")
    assert row.id == 1
    listed = store.list_all()
    assert len(listed) == 1
    found = store.search("内容")
    assert found[0].id == 1
    assert store.delete(1)
    assert store.list_all() == []


def test_task_store_add_list(tmp_path: Path):
    db = tmp_path / "task.db"
    store = TaskStore(db)
    row = store.add("任务1", "做某事", tags=["work"], status="pending")
    assert row.id == 1
    text = handle_task_command("list", store)
    assert "任务1" in text
    assert store.delete(1)


def test_note_keyword_search(tmp_path: Path):
    db = tmp_path / "note.db"
    store = NoteStore(db)
    store.add("测试标题", "正文内容")
    store.add("其他", "无关")
    result = handle_note_command("测试", store)
    assert "笔记搜索" in result
    assert "| 1 |" in result
    assert "创建时间" in result
    add_result = handle_note_command("add 新标题 新内容", store)
    assert "已添加笔记" in add_result


def test_cache_admin_list_and_rm(tmp_path: Path):
    db = tmp_path / "cache.db"
    store = SearchCacheStore(db)
    store.upsert(
        cache_key="testquery",
        search_query="测试标题",
        response="x" * 120,
        user_query="用户问",
        search_ok=True,
        ttl_days=7,
        max_user_queries=5,
    )
    cache = SearchCache(db_path=db)
    listed = handle_cache_command("list", cache)
    cid = cache_display_id("testquery")
    assert cid in listed
    assert "测试标题" in listed
    rm = handle_cache_command(f"rm {cid}", cache)
    assert "已删除" in rm
    assert "暂无" in handle_cache_command("list", cache) or "暂无缓存" in handle_cache_command("list", cache)
