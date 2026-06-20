"""open_local 路径清理测试。"""

from __future__ import annotations

from pathlib import Path

from src.ui.open_local import check_local_paths, clean_local_path, local_path_exists, open_local_path


def test_clean_local_path():
    assert clean_local_path('"D:\\tmp\\a.xlsx"') == "D:\\tmp\\a.xlsx"
    assert clean_local_path("D:\\tmp\\a.xlsx。") == "D:\\tmp\\a.xlsx"
    assert clean_local_path("D:\\tmp\\a.xlsx)") == "D:\\tmp\\a.xlsx"


def test_open_local_path_missing(tmp_path):
    missing = tmp_path / "missing.txt"
    result = open_local_path(str(missing))
    assert result["ok"] is False
    assert "不存在" in result["error"]


def test_open_local_path_file(tmp_path):
    f = tmp_path / "demo.txt"
    f.write_text("hello", encoding="utf-8")
    result = open_local_path(str(f))
    assert result["ok"] is True
    assert Path(result["path"]) == f.resolve()


def test_local_path_exists(tmp_path):
    f = tmp_path / "demo.txt"
    f.write_text("hello", encoding="utf-8")
    missing = tmp_path / "missing.txt"
    assert local_path_exists(str(f)) is True
    assert local_path_exists(str(missing)) is False


def test_check_local_paths(tmp_path):
    f = tmp_path / "demo.txt"
    f.write_text("hello", encoding="utf-8")
    missing = tmp_path / "missing.txt"
    result = check_local_paths([str(f), str(missing), str(f)])
    assert result[str(f)] is True
    assert result[str(missing)] is False
    assert len(result) == 2
