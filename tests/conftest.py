from __future__ import annotations

import pytest


@pytest.fixture
def fs_env(tmp_path, monkeypatch):
    """可写的隔离文件系统环境，file 工具包各模块共享。"""
    import src.infra.files_config as fc
    import src.tools.file.advanced as advanced_mod
    import src.tools.file.meta as meta_mod
    import src.tools.file.ops as ops_mod
    import src.tools.file.path as path_mod
    import src.tools.file.search as search_mod

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "hello.py").write_text('print("hello")\n# TODO: fix\n', encoding="utf-8")
    (workspace / "readme.md").write_text("# Project\nsearch keyword here\n", encoding="utf-8")
    (workspace / "data").mkdir()
    (workspace / "data" / "notes.txt").write_text("local search test content\n", encoding="utf-8")

    trash = tmp_path / "trash"
    trash.mkdir()

    def roots():
        return [workspace]

    def fake_option(key, default):
        opts = {
            "max_results": 80,
            "max_depth": 12,
            "max_file_size_mb": 5,
            "grep_context_lines": 2,
            "prefer_cli": False,
            "exclude_dirs": [".git"],
            "grep_globs": ["*.txt", "*.md", "*.py"],
        }
        return opts.get(key, default)

    for mod in (fc, path_mod, ops_mod, meta_mod, advanced_mod, search_mod):
        monkeypatch.setattr(mod, "get_search_roots", roots, raising=False)
        monkeypatch.setattr(mod, "get_fs_option", fake_option, raising=False)

    monkeypatch.setattr(path_mod, "trash_directory", lambda: trash)
    monkeypatch.setattr(ops_mod, "trash_directory", lambda: trash)

    return workspace
