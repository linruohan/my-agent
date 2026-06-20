"""Skill 执行器 LLM 意图集成测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from src.ui.skill_runner import run_skill


class _FakeLLM:
    def __init__(self, content: str) -> None:
        self._content = content

    def invoke(self, messages):  # noqa: ANN001
        return SimpleNamespace(content=self._content)


def test_run_skill_uses_llm_parsed_args(tmp_path, monkeypatch):
    skill_root = tmp_path / "docx-py"
    scripts = skill_root / "scripts"
    scripts.mkdir(parents=True)
    entry = scripts / "create_docx.py"
    entry.write_text(
        "import argparse\nfrom pathlib import Path\n"
        "p=argparse.ArgumentParser()\n"
        "p.add_argument('--output','-o',required=True)\n"
        "p.add_argument('--text','-t',default='')\n"
        "a=p.parse_args()\n"
        "Path(a.output).write_text('ok')\n"
        "print('done', a.output, a.text)\n",
        encoding="utf-8",
    )
    (skill_root / "SKILL.md").write_text(
        """
## 命令行使用
```bash
python scripts/create_docx.py --output out.docx --text hello
```
| 参数 | 简写 | 必填 | 说明 |
|------|------|------|------|
| `--output` | `-o` | 是 | 输出路径 |
| `--text` | `-t` | 否 | 文本 |
scripts/create_docx.py
""",
        encoding="utf-8",
    )

    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    out_file = desktop / "123.docx"
    out_path = str(out_file).replace("\\", "/")
    llm = _FakeLLM(
        f'{{"cli_args":"--output \\"{out_path}\\" --text 123","reason":"解析桌面 docx"}}'
    )

    with patch("src.ui.skill_runner.resolve_skill") as resolve:
        resolve.return_value = (skill_root, skill_root / "SKILL.md")
        result = run_skill("docx-py", "桌面新建一个docx 内容是123", llm=llm)

    assert result.ok is True
    assert result.intent_reason == "解析桌面 docx"
    assert out_file.is_file()
