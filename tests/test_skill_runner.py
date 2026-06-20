"""Skill 执行器测试。"""

from __future__ import annotations

from src.ui.skill_runner import _build_argv, _extract_section, _find_entry_script


def test_extract_section():
    assert _extract_section("获取 2.1 章节的表格") == "2.1"
    assert _extract_section('获取 "6.1 富文本单元格"') == "6.1 富文本单元格"


def test_build_argv_doc_diff(tmp_path):
    skill_root = tmp_path / "doc-diff-tool"
    scripts = skill_root / "scripts"
    scripts.mkdir(parents)
    entry = scripts / "doc_diff_tool.py"
    entry.write_text("if __name__ == '__main__': pass", encoding="utf-8")

    docx = skill_root / "tests"
    docx.mkdir()
    test_file = docx / "test.docx"
    test_file.write_bytes(b"x")

    skill_text = "scripts/doc_diff_tool.py 主程序"
    assert _find_entry_script(skill_root, skill_text) == entry

    user_args = f'"{test_file}" 获取 2.1 章节的表格'
    argv = _build_argv(entry, user_args, skill_root)
    assert argv is not None
    assert argv[0] == str(test_file.resolve())
    assert argv[1:3] == ["--section", "2.1"]
    assert argv[3] == "--output"
