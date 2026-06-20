from __future__ import annotations

import pytest

from src.tools.file.path import PathNotAllowedError
from src.tools.file.search import (
    _parse_rg_match_line,
    _parse_rg_output,
    find_files_impl,
    grep_files_impl,
    list_directory_impl,
    read_local_file_impl,
)


def test_find_files_by_pattern(fs_env):
    result = find_files_impl("*.py", str(fs_env))
    assert "hello.py" in result
    assert "文件搜索" in result


def test_parse_rg_match_line_windows_path():
    line = r"D:\codehub\my-agent\tests\conftest.py:8:    可写的隔离文件系统环境。"
    parsed = _parse_rg_match_line(line)
    assert parsed is not None
    path, line_no, content = parsed
    assert path == r"D:\codehub\my-agent\tests\conftest.py"
    assert line_no == 8
    assert "文件系统" in content


def test_parse_rg_output_with_context():
    stdout = (
        r"D:\proj\tests\conftest.py-6-@pytest.fixture" + "\n"
        r"D:\proj\tests\conftest.py:8:    文件系统"
    )
    hits = _parse_rg_output(stdout, context=2)
    assert len(hits) == 1
    assert hits[0].line_no == 8
    assert hits[0].context_before == ["@pytest.fixture"]


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
    import src.tools.file.path as path_mod

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setattr(fc, "get_search_roots", lambda: [allowed])
    monkeypatch.setattr(path_mod, "get_search_roots", lambda: [allowed])

    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(PathNotAllowedError):
        read_local_file_impl(str(outside))
