"""使用 LLM 将 Skill 自然语言请求解析为 CLI 参数。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger


@dataclass
class SkillIntentParseResult:
    ok: bool
    cli_args: str = ""
    reason: str = ""
    error: str = ""


def _parse_llm_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {}


def _extract_skill_cli_context(skill_text: str, *, max_chars: int = 6000) -> str:
    """提取 SKILL.md 中与命令行相关的段落。"""
    text = skill_text or ""
    markers = ("命令行", "CLI", "参数说明", "使用示例", "快速创建")
    start = -1
    for marker in markers:
        idx = text.find(marker)
        if idx >= 0:
            start = idx if start < 0 else min(start, idx)
    if start < 0:
        start = 0
    chunk = text[start : start + max_chars].strip()
    return chunk or text[:max_chars]


def _desktop_path() -> str:
    desktop = Path.home() / "Desktop"
    if not desktop.is_dir():
        alt = Path.home() / "桌面"
        if alt.is_dir():
            desktop = alt
    return str(desktop)


def _build_skill_intent_prompt(skill_name: str, skill_text: str, user_args: str) -> str:
    cli_ctx = _extract_skill_cli_context(skill_text)
    return f"""Skill 名称：{skill_name}

【SKILL.md 命令行说明（节选）】
{cli_ctx}

【环境信息】
- 用户主目录：{Path.home()}
- 桌面路径：{_desktop_path()}
- 请将「桌面」类描述解析为桌面绝对路径

【用户请求】
{user_args.strip() or "（无额外参数）"}

请根据 SKILL.md 的命令行参数说明，把用户请求转换为可直接传给脚本的 CLI 参数字符串。
只返回 JSON（不要 markdown）：
{{"cli_args":"--flag value ...","reason":"一句话说明解析结果"}}

规则：
1. cli_args 只包含脚本参数，不要包含 python 或脚本文件名
2. 路径含空格时用双引号包裹
3. 必填参数必须给出；可选参数仅在用户明确需要时填写
4. 无法从 SKILL 说明推断出可执行参数时：{{"cli_args":"","reason":"原因","fallback":true}}
"""


def parse_skill_command_with_llm(
    llm: BaseChatModel,
    skill_name: str,
    skill_text: str,
    user_args: str,
) -> SkillIntentParseResult:
    """用 LLM 将自然语言 Skill 请求解析为 CLI 参数字符串。"""
    body = (user_args or "").strip()
    if not body:
        return SkillIntentParseResult(ok=False, error="用户参数为空")

    try:
        msg = llm.invoke(
            [
                SystemMessage(content="你是 Skill 命令行参数解析器，只输出 JSON。"),
                HumanMessage(content=_build_skill_intent_prompt(skill_name, skill_text, body)),
            ]
        )
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        data = _parse_llm_json(content)
    except Exception as exc:
        logger.exception("Skill LLM 意图识别失败")
        return SkillIntentParseResult(ok=False, error=f"LLM 意图识别失败: {exc}")

    if data.get("fallback"):
        reason = str(data.get("reason") or "无法解析为 CLI 参数").strip()
        return SkillIntentParseResult(ok=False, error=reason, reason=reason)

    cli_args = str(data.get("cli_args") or "").strip()
    reason = str(data.get("reason") or "llm").strip()
    if not cli_args:
        err = reason or "LLM 未返回 cli_args"
        return SkillIntentParseResult(ok=False, error=err, reason=reason)

    return SkillIntentParseResult(ok=True, cli_args=cli_args, reason=reason)
