def test_memory_injection_prefers_recent_tail(tmp_path, monkeypatch):
    from src.memory.context_files import build_memory_prompt_block, memory_file_path, write_context_file

    monkeypatch.setattr("src.memory.context_files.workspace_dir", lambda: tmp_path)
    path = memory_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    old = "旧条目\n" * 1200
    recent = "最新记忆条目"
    write_context_file(path, old + recent, mode="replace")

    block = build_memory_prompt_block()
    assert "最新记忆条目" in block
    assert "旧条目" not in block or "前文已截断" in block
