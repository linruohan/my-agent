from __future__ import annotations

from pathlib import Path

import pytest

from src.tools.files import (
    PathNotAllowedError,
    find_files_impl,
    grep_files_impl,
    list_directory_impl,
    read_local_file_impl,
)


@pytest.fixture
def fs_env(tmp_path, monkeypatch):
    import src.infra.files_config as fc
    import src.tools.files as files_mod

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "hello.py").write_text('print("hello")\n# TODO: fix\n', encoding="utf-8")
    (workspace / "readme.md").write_text("# Project\nsearch keyword here\n", encoding="utf-8")
    (workspace / "data").mkdir()
    (workspace / "data" / "notes.txt").write_text("local search test content\n", encoding="utf-8")

    monkeypatch.setattr(fc, "get_search_roots", lambda: [workspace])
    monkeypatch.setattr(files_mod, "get_search_roots", lambda: [workspace])

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

    monkeypatch.setattr(files_mod, "get_fs_option", fake_option)
    return workspace


def test_find_files_by_pattern(fs_env):
    result = find_files_impl("*.py", str(fs_env))
    assert "hello.py" in result
    assert "文件搜索" in result


def test_grep_files_content(fs_env):
    result = grep_files_impl("keyword", str(fs_env))
    assert "readme.md" in result
    assert "keyword" in result


def test_list_directory(fs_env):
    result = list_directory_impl(str(fs_env))
    assert "hello.py" in result
    assert "data" in result


def test_read_local_file(fs_env):
    f = fs_env / "hello.py"
    result = read_local_file_impl(str(f))
    assert 'print("hello")' in result


def test_path_not_allowed(tmp_path, monkeypatch):
    import src.infra.files_config as fc
    import src.tools.files as files_mod

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setattr(fc, "get_search_roots", lambda: [allowed])
    monkeypatch.setattr(files_mod, "get_search_roots", lambda: [allowed])

    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(PathNotAllowedError):
        read_local_file_impl(str(outside))
