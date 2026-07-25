"""任务文本解析测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from unittest.mock import patch

import pytest

from src.tools.task.defaults import DEFAULT_REMIND_SPEC, build_remind_schedule, get_default_owner_name
from src.tools.task.parse import (
    calc_remind_at,
    parse_due_datetime,
    parse_repeat_end,
    parse_repeat_token,
    parse_task_add,
    parse_task_add_with_defaults,
    parse_task_edit,
    tokenize_task_text,
)
from src.tools.task.commands import handle_task_command
from src.tools.task.store import TaskStore

TZ = timezone(timedelta(hours=8))
REF = datetime(2026, 6, 21, 10, 0, tzinfo=TZ)


def test_tokenize_splits_cn_punctuation():
    tokens = tokenize_task_text("写报告，整理素材；@{张三}、#{urgent}")
    assert tokens == ["写报告", "整理素材", "@{张三}", "#{urgent}"]


def test_parse_due_today_time():
    dt = parse_due_datetime("17:30", REF)
    assert dt.hour == 17 and dt.minute == 30 and dt.day == 21


def test_parse_due_full_datetime():
    dt = parse_due_datetime("2026.06.21.17:30", REF)
    assert dt.year == 2026 and dt.month == 6 and dt.day == 21
    assert dt.hour == 17 and dt.minute == 30


def test_parse_due_tomorrow_eod():
    dt = parse_due_datetime("明天下班前", REF)
    assert dt.day == 22 and dt.hour == 17 and dt.minute == 30


def test_parse_due_tomorrow_morning():
    dt = parse_due_datetime("明天上班前", REF)
    assert dt.day == 22 and dt.hour == 9 and dt.minute == 0


def test_parse_due_month_day():
    dt = parse_due_datetime("6.22", REF)
    assert dt.month == 6 and dt.day == 22 and dt.hour == 17 and dt.minute == 30


def test_parse_due_short_year():
    dt = parse_due_datetime("26.5.21.17:30", REF)
    assert dt.year == 2026 and dt.month == 5 and dt.day == 21


def test_calc_remind_offsets():
    due = datetime(2026, 6, 21, 17, 30, tzinfo=TZ)
    assert calc_remind_at(due, "1m").minute == 29
    assert calc_remind_at(due, "1h").hour == 16
    rem_d = calc_remind_at(due, "1d")
    assert rem_d.day == 20 and rem_d.hour == 9


def test_parse_repeat_end():
    assert parse_repeat_end("none", REF) == "none"
    assert parse_repeat_end("3", REF) == "3"
    end = parse_repeat_end("5.21.17:30", REF)
    assert "2026-05-21" in end


def test_parse_task_add_full():
    text = "完成报告 整理素材 @{张三} #{urgent} #{work} @due-明天下班前 @rem-1h @rep-1day-2 @rep-end-none"
    parsed = parse_task_add_with_defaults(text, ref=REF)
    assert parsed["title"] == "完成报告"
    assert parsed["content"] == "整理素材"
    assert parsed["owner"] == "张三"
    assert parsed["tags"] == ["urgent", "work"]
    assert parsed["due_at"] is not None
    assert parsed["remind_at"] is not None
    assert parsed["repeat_rule"] is not None
    assert parsed["repeat_end"] == "none"


def test_parse_repeat_token_variants():
    assert parse_repeat_token("@rep-1day-2") == (1, "day", 2)
    assert parse_repeat_token("@rep-day") == (1, "day", 1)
    assert parse_repeat_token("@rep-day-3") == (1, "day", 3)
    assert parse_repeat_token("@rep-2week") == (2, "week", 1)


def test_parse_task_add_defaults_minimal():
    parsed = parse_task_add_with_defaults("写周报", ref=REF)
    assert parsed["title"] == "写周报"
    assert parsed["owner"] == get_default_owner_name()
    assert parsed["due_at"] is not None
    due = datetime.fromisoformat(parsed["due_at"])
    assert due.hour == 17 and due.minute == 30
    assert parsed["remind_spec"] == DEFAULT_REMIND_SPEC
    assert len(parsed.get("remind_schedule") or []) >= 1
    assert parsed.get("repeat_rule") is None


def test_parse_task_add_no_repeat_without_rep_marker():
    parsed = parse_task_add_with_defaults("简单任务", ref=REF)
    assert parsed.get("repeat_rule") is None
    assert parsed.get("repeat_end") is None


def test_parse_task_edit_only_markers():
    parsed = parse_task_edit("@{李四} @due-17:30", ref=REF)
    assert parsed.title is None
    assert parsed.owner == "李四"
    assert parsed.due_set is True


def test_handle_task_add_and_edit(tmp_path: Path):
    store = TaskStore(tmp_path / "task.db")
    add_text = "写文档 @{me} #{work} @due-6.22 @rem-1d"
    result = handle_task_command(f"add {add_text}", store)
    assert "已添加任务 #1" in result

    listed = handle_task_command("list", store)
    assert "| ID | 标题 | 负责人 | 截止 |" in listed
    assert "| 附件 |" in listed
    assert "me" in listed
    assert "work" in listed

    row = store.get(1)
    assert row is not None
    assert row.owner == "me"
    assert "work" in row.tags
    assert row.due_at is not None
    assert row.remind_at is not None

    mod_result = handle_task_command("mod 1 @{team}", store)
    assert "已更新任务" in mod_result
    row = store.get(1)
    assert row.owner == "team"


def test_parse_task_edit_absolute_remind():
    parsed = parse_task_edit("@rem-6.22.10:00", ref=REF)
    assert parsed.remind_set is True
    assert parsed.remind_absolute is True
    assert parsed.remind_spec is None
    dt = datetime.fromisoformat(parsed.remind_at)
    assert dt.month == 6 and dt.day == 22 and dt.hour == 10 and dt.minute == 0


def test_parse_task_edit_offset_remind_still_works():
    parsed = parse_task_edit("@rem-1h", ref=REF)
    assert parsed.remind_set is True
    assert parsed.remind_absolute is False
    assert parsed.remind_spec == "1h"


def test_handle_task_mod_append_absolute_remind(tmp_path: Path):
    store = TaskStore(tmp_path / "task.db")
    handle_task_command("add 测试任务", store)
    row = store.get(1)
    assert row is not None
    initial_count = len(row.remind_schedule)

    result = handle_task_command("mod 1 @rem-6.25.09:30", store)
    assert "已更新任务" in result
    updated = store.get(1)
    assert updated is not None
    assert len(updated.remind_schedule) == initial_count + 1
    assert any("2026-06-25" in s and "09:30" in s for s in updated.remind_schedule)

    # 重复追加同一时间点不应重复
    handle_task_command("mod 1 @rem-6.25.09:30", store)
    again = store.get(1)
    assert len(again.remind_schedule) == len(updated.remind_schedule)


def test_handle_task_add_absolute_remind(tmp_path: Path):
    store = TaskStore(tmp_path / "task.db")
    handle_task_command("add 定时提醒 @rem-6.23.15:00", store)
    row = store.get(1)
    assert row is not None
    assert len(row.remind_schedule) == 1
    dt = datetime.fromisoformat(row.remind_schedule[0])
    assert dt.month == 6 and dt.day == 23 and dt.hour == 15


def test_default_remind_fallback_same_day():
    due = REF.replace(hour=17, minute=30)
    schedule = build_remind_schedule(due, DEFAULT_REMIND_SPEC, ref=REF)
    assert len(schedule) >= 1
    dt = datetime.fromisoformat(schedule[0])
    assert dt < due


def test_handle_task_notify_and_tick(tmp_path: Path):
    store = TaskStore(tmp_path / "task.db")
    now = datetime.now().astimezone()
    past = (now - timedelta(minutes=1)).isoformat()
    row = store.add(
        "即时提醒",
        "内容",
        due_at=(now + timedelta(hours=2)).isoformat(),
        remind_at=past,
        remind_schedule=[past],
    )

    with patch("src.tools.task.scheduler.send_task_toast", return_value=True) as toast:
        msg = handle_task_command("notify", store)
        assert "测试通知" in msg

        msg2 = handle_task_command(f"notify {row.id}", store)
        assert "已发送提醒" in msg2
        assert toast.call_count == 0  # notify 走 notify 模块，非 scheduler

    with patch("src.tools.task.notify.send_task_toast", return_value=True):
        msg3 = handle_task_command("tick", store)
        assert "已处理提醒" in msg3
        updated = store.get(row.id)
        assert updated is not None
        assert updated.remind_at is None


def test_handle_task_mod_requires_id(tmp_path: Path):
    store = TaskStore(tmp_path / "task.db")
    assert "任务 ID" in handle_task_command("mod", store)
    assert "任务 ID" in handle_task_command("mod abc 改标题", store)


def test_handle_task_add_requires_title(tmp_path: Path):
    store = TaskStore(tmp_path / "task.db")
    msg = handle_task_command("add @{only}", store)
    assert "标题" in msg or "不能为空" in msg
