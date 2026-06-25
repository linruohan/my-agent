from __future__ import annotations

from unittest.mock import patch

from src.agent.learning import apply_learning, learning_loop_config
from src.tools.code.tool_rpc import invoke_sandbox_tool, sandbox_allowed_tools


def test_sandbox_allowed_tools_includes_read_only():
    names = sandbox_allowed_tools()
    assert "list_tasks" in names
    assert "write_local_file" not in names


def test_invoke_sandbox_tool_blocks_write():
    out = invoke_sandbox_tool("write_local_file", {"path": "x", "content": "y"})
    assert "不允许" in out


def test_invoke_sandbox_tool_list_tasks(tmp_path, monkeypatch):
    db = tmp_path / "task.db"
    store_cls = __import__("src.tools.task.store", fromlist=["TaskStore"]).TaskStore
    monkeypatch.setattr("src.tools.task.tools.TaskStore", lambda: store_cls(db))
    out = invoke_sandbox_tool("list_tasks", {})
    assert "任务" in out or "没有" in out


def test_learning_loop_config_defaults():
    cfg = learning_loop_config()
    assert "enabled" in cfg
    assert cfg["min_tool_calls"] >= 1


def test_apply_learning_create_skill(tmp_path, monkeypatch):
    monkeypatch.setattr("src.ui.skill.writer.default_skills_dir", lambda: tmp_path / "skills")
    monkeypatch.setattr(
        "src.ui.skill.writer.get_skill_dirs",
        lambda: [tmp_path / "skills"],
    )
    monkeypatch.setattr("src.ui.skill.writer.resolve_skill", lambda _n: None)
    analysis = {
        "save_skill": True,
        "skill_name": "auto-demo",
        "description": "演示",
        "instructions": "步骤一",
        "memory_note": "",
    }
    msg = apply_learning(analysis, auto_create_skill=True, auto_update_memory=False)
    assert msg and "Skill" in msg


def test_execute_code_with_call_tool(tmp_path, monkeypatch):
    monkeypatch.setattr("src.tools.code.sandbox._SESSION_DIR", tmp_path)
    monkeypatch.setattr("src.tools.code.sandbox.sandbox_tool_call_enabled", lambda: True)

    def fake_invoke(name, args=None):
        if name == "list_tasks":
            return "任务 A"
        return "unknown"

    monkeypatch.setattr("src.tools.code.sandbox.invoke_sandbox_tool", fake_invoke)
    from src.tools.code.sandbox import execute_code_in_sandbox

    code = 'result = call_tool("list_tasks")\nprint(result)'
    out = execute_code_in_sandbox(code, session_id="rpc-test")
    assert "任务 A" in out
