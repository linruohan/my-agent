"""Skill LLM 意图解析测试。"""

from __future__ import annotations

from types import SimpleNamespace

from src.ui.skill.intent import parse_skill_command_with_llm


class _FakeLLM:
    def __init__(self, content: str) -> None:
        self._content = content

    def invoke(self, messages):  # noqa: ANN001
        return SimpleNamespace(content=self._content)


DOCX_SKILL_MD = """
## 命令行使用
| 参数 | 简写 | 必填 | 说明 |
|------|------|------|------|
| `--output` | `-o` | 是 | 输出 .docx 文件路径 |
| `--text` | `-t` | 否 | 段落文本 |
"""


def test_parse_skill_command_with_llm_success():
    llm = _FakeLLM(
        '{"cli_args":"--output \\"C:\\\\Users\\\\me\\\\Desktop\\\\123.docx\\" --text 123","reason":"桌面创建 docx"}'
    )
    result = parse_skill_command_with_llm(
        llm,
        "docx-py",
        DOCX_SKILL_MD,
        "桌面新建一个docx 内容是123",
    )
    assert result.ok is True
    assert "--output" in result.cli_args
    assert "--text 123" in result.cli_args
    assert result.reason == "桌面创建 docx"


def test_parse_skill_command_with_llm_fallback():
    llm = _FakeLLM('{"cli_args":"","reason":"缺少输出路径","fallback":true}')
    result = parse_skill_command_with_llm(llm, "docx-py", DOCX_SKILL_MD, "帮我写文档")
    assert result.ok is False
    assert result.error
