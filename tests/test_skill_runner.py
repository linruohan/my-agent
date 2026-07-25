"""Skill 执行器测试（通用 CLI 解析）。"""

from __future__ import annotations

from pathlib import Path

from src.ui.skill.runner import (
    CliSpec,
    _build_argv,
    _collect_free_values,
    _find_entry_script,
    _parse_cli_spec_from_skill,
    _parse_natural_hints,
    _resolve_cli_spec,
)

DOC_DIFF_SKILL_MD = """
## 命令行使用

```bash
python scripts/doc_diff_tool.py test.docx --section "1. 概述" --output result.xlsx
```

| 参数 | 简写 | 必填 | 说明 |
|------|------|------|------|
| `input_file` | - | 是 | 输入的文档文件路径 |
| `--section` | `-s` | 是 | 要提取的章节标题或编号 |
| `--output` | `-o` | 否 | 输出的 Excel 文件路径 |
"""


def test_parse_cli_spec_from_skill_md():
    spec = _parse_cli_spec_from_skill(DOC_DIFF_SKILL_MD, "doc_diff_tool.py")
    assert spec is not None
    assert len(spec.params) == 3
    assert spec.params[0].positional and spec.params[0].required
    assert spec.params[1].name == "--section" and spec.params[1].required
    assert spec.params[2].name == "--output" and not spec.params[2].required


def test_collect_free_values():
    values = _collect_free_values("获取 2.1 章节的表格", [], [])
    assert values == ["2.1 章节"]

    values = _collect_free_values('获取"章节 2"', [], ["章节 2"])
    assert values == ["章节 2"]


def test_build_argv_from_skill_md(tmp_path):
    skill_root = tmp_path / "doc-diff-tool"
    scripts = skill_root / "scripts"
    scripts.mkdir(parents=True)
    entry = scripts / "doc_diff_tool.py"
    entry.write_text("if __name__ == '__main__': pass", encoding="utf-8")

    tests_dir = skill_root / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test.docx"
    test_file.write_bytes(b"x")

    skill_text = DOC_DIFF_SKILL_MD + "\nscripts/doc_diff_tool.py 主程序"
    assert _find_entry_script(skill_root, skill_text) == entry

    user_args = f'"{test_file}" 获取 2.1 章节的表格'
    argv = _build_argv(entry, user_args, skill_text, skill_root)
    assert argv is not None
    assert argv[0] == str(test_file.resolve())
    assert argv[1:3] == ["--section", "2.1 章节"]
    assert "--output" not in argv


def test_build_argv_raw_cli(tmp_path):
    skill_root = tmp_path / "demo-skill"
    scripts = skill_root / "scripts"
    scripts.mkdir(parents=True)
    entry = scripts / "main.py"
    entry.write_text("if __name__ == '__main__': pass", encoding="utf-8")

    skill_text = """
| 参数 | 简写 | 必填 | 说明 |
|------|------|------|------|
| `--input` | `-i` | 是 | 输入 |
"""
    argv = _build_argv(entry, '--input "a.txt" --verbose', skill_text, skill_root)
    assert argv == ["--input", "a.txt", "--verbose"]


DOCX_SKILL_MD = """
## 命令行使用

```bash
python scripts/create_docx.py --output ~/Desktop/example.docx --text "文档内容"
```

| 参数 | 简写 | 必填 | 说明 |
|------|------|------|------|
| `--output` | `-o` | 是 | 输出 .docx 文件路径 |
| `--text` | `-t` | 否 | 写入文档的段落文本 |
"""


def test_build_argv_docx_natural_language(tmp_path, monkeypatch):
    skill_root = tmp_path / "docx-py"
    scripts = skill_root / "scripts"
    scripts.mkdir(parents=True)
    entry = scripts / "create_docx.py"
    entry.write_text("if __name__ == '__main__': pass", encoding="utf-8")

    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    skill_text = DOCX_SKILL_MD + "\nscripts/create_docx.py"
    argv = _build_argv(entry, "桌面新建一个docx 内容是123", skill_text, skill_root)
    assert argv is not None
    assert argv[0:2] == ["--output", str(desktop / "123.docx")]
    assert argv[2:4] == ["--text", "123"]


def test_parse_natural_hints():
    hints = _parse_natural_hints("桌面新建一个docx 内容是123")
    assert hints["text"] == "123"
    assert "desktop_dir" in hints


def test_resolve_cli_spec_prefers_skill_md(tmp_path):
    entry = tmp_path / "tool.py"
    entry.write_text("if __name__ == '__main__': pass", encoding="utf-8")
    spec = _resolve_cli_spec(DOC_DIFF_SKILL_MD, entry)
    assert isinstance(spec, CliSpec)
    assert any(p.name == "--section" for p in spec.params)
