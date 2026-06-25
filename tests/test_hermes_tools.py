from __future__ import annotations

from src.tools import ALL_TOOLS, TOOL_BY_NAME


def test_hermes_tools_registered():
    names = {t.name for t in ALL_TOOLS}
    expected = {
        "read_user_profile",
        "update_user_profile",
        "read_agent_memory",
        "update_agent_memory",
        "search_past_conversations",
        "list_skills",
        "get_skill_details",
        "run_skill_tool",
        "list_cron_jobs",
        "add_cron_job",
        "pause_cron_job",
        "resume_cron_job",
        "delete_cron_job",
    }
    missing = expected - names
    assert not missing, f"missing tools: {missing}"


def test_memory_tools_invoke(tmp_path, monkeypatch):
    monkeypatch.setattr("src.memory.context_files.workspace_dir", lambda: tmp_path)
    from src.memory.context_files import ensure_context_files
    from src.tools.memory.tools import read_user_profile, update_agent_memory

    ensure_context_files()
    out = update_agent_memory.invoke({"content": "- 测试记忆条目", "mode": "append"})
    assert "MEMORY.md" in out
    from src.tools.memory.tools import read_agent_memory

    mem = read_agent_memory.invoke({})
    assert "测试记忆条目" in mem
