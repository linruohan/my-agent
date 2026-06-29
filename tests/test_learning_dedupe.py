"""学习闭环去重测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.agent.learning import apply_learning, learning_loop_config, maybe_learn_from_turn
from src.agent.learning_dedupe import (
    LearningLedger,
    memory_note_exists,
    normalize_memory_line,
    skill_instructions_exist,
    turn_fingerprint,
)


def test_turn_fingerprint_stable():
    tools = [{"name": "web_search", "args": {"q": "a"}}, {"name": "list_tasks", "args": {}}]
    fp1 = turn_fingerprint("帮我总结任务", tools)
    fp2 = turn_fingerprint("帮我总结任务", tools)
    fp3 = turn_fingerprint("帮我总结任务", [{"name": "list_tasks", "args": {}}])
    fp4 = turn_fingerprint("帮我总结任务", [{"name": "web_search", "args": {"q": "b"}}, {"name": "list_tasks", "args": {}}])
    assert fp1 == fp2
    assert fp1 != fp3
    assert fp1 != fp4


def test_turn_fingerprint_includes_args():
    tools_a = [{"name": "web_search", "args": {"query": "foo"}}]
    tools_b = [{"name": "web_search", "args": {"query": "bar"}}]
    assert turn_fingerprint("q", tools_a) != turn_fingerprint("q", tools_b)


def test_turn_fingerprint_args_key_order_irrelevant():
    tools_a = [{"name": "web_search", "args": {"q": "x", "limit": 5}}]
    tools_b = [{"name": "web_search", "args": {"limit": 5, "q": "x"}}]
    assert turn_fingerprint("q", tools_a) == turn_fingerprint("q", tools_b)


def test_memory_note_exists(tmp_path, monkeypatch):
    mem = tmp_path / "MEMORY.md"
    mem.write_text("# Agent 记忆\n\n- 用户偏好深色主题\n", encoding="utf-8")
    monkeypatch.setattr("src.agent.learning_dedupe.memory_file_path", lambda: mem)
    assert memory_note_exists("用户偏好深色主题")
    assert memory_note_exists("- 用户偏好深色主题")
    assert not memory_note_exists("完全不同的内容")


def test_skill_instructions_exist(tmp_path, monkeypatch):
    skill_root = tmp_path / "skills" / "demo-skill"
    skill_root.mkdir(parents=True)
    skill_md = skill_root / "SKILL.md"
    skill_md.write_text("# Demo\n\n步骤一：打开文件\n", encoding="utf-8")
    monkeypatch.setattr("src.ui.skill.catalog.get_skill_dirs", lambda: [tmp_path / "skills"])
    monkeypatch.setattr(
        "src.ui.skill.catalog.resolve_skill",
        lambda name: (skill_root, skill_md) if name == "demo-skill" else None,
    )
    monkeypatch.setattr(
        "src.agent.learning_dedupe.resolve_skill",
        lambda name: (skill_root, skill_md) if name == "demo-skill" else None,
    )
    assert skill_instructions_exist("demo-skill", "步骤一：打开文件")
    assert not skill_instructions_exist("demo-skill", "全新步骤说明")


def test_apply_learning_skips_duplicate_memory(tmp_path, monkeypatch):
    mem = tmp_path / "MEMORY.md"
    mem.write_text("- 已有事实\n", encoding="utf-8")
    monkeypatch.setattr("src.agent.learning_dedupe.memory_file_path", lambda: mem)
    analysis = {"save_skill": False, "memory_note": "已有事实"}
    msg = apply_learning(analysis, auto_create_skill=False, auto_update_memory=True)
    assert msg is None


def test_apply_learning_skips_duplicate_skill(tmp_path, monkeypatch):
    skill_root = tmp_path / "skills" / "auto-demo"
    skill_root.mkdir(parents=True)
    skill_md = skill_root / "SKILL.md"
    skill_md.write_text("# Demo\n\n步骤一\n", encoding="utf-8")
    monkeypatch.setattr("src.ui.skill.catalog.get_skill_dirs", lambda: [tmp_path / "skills"])
    monkeypatch.setattr(
        "src.ui.skill.catalog.resolve_skill",
        lambda name: (skill_root, skill_md) if name == "auto-demo" else None,
    )
    monkeypatch.setattr(
        "src.agent.learning_dedupe.resolve_skill",
        lambda name: (skill_root, skill_md) if name == "auto-demo" else None,
    )
    monkeypatch.setattr("src.ui.skill.writer.default_skills_dir", lambda: tmp_path / "skills")
    analysis = {
        "save_skill": True,
        "skill_name": "auto-demo",
        "description": "演示",
        "instructions": "步骤一",
        "memory_note": "",
    }
    msg = apply_learning(analysis, auto_create_skill=True, auto_update_memory=False)
    assert msg is None


def test_maybe_learn_skips_duplicate_fingerprint(tmp_path, monkeypatch):
    db = tmp_path / "learning.db"
    monkeypatch.setattr("src.agent.learning.shared_ledger", lambda: LearningLedger(db))

    llm = MagicMock()
    tools = [{"name": "a", "args": {}}, {"name": "b", "args": {}}, {"name": "c", "args": {}}]
    fp = turn_fingerprint("用户问题", tools)
    LearningLedger(db).record(fp, skill_name="x", memory_note="y")

    with patch("src.agent.learning.analyze_turn_for_learning") as analyze:
        result = maybe_learn_from_turn(
            llm,
            user_message="用户问题",
            assistant_message="助手回复",
            tool_calls=tools,
        )
        assert result is None
        analyze.assert_not_called()


def test_learning_loop_config_dedupe_default():
    cfg = learning_loop_config()
    assert cfg["dedupe_enabled"] is True


def test_normalize_memory_line():
    assert normalize_memory_line("-  Hello  ") == "hello"
