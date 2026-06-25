"""LangChain 工具：Skill 一等公民（Agent 可发现、查询、执行 Skill）。"""

from __future__ import annotations

from langchain_core.tools import tool

from src.ui.skill.catalog import load_skill_prompt, scan_skills
from src.ui.skill.runner import can_run_skill, run_skill
from src.ui.skill.writer import create_skill_files, update_skill_instructions


@tool
def list_skills() -> str:
    """列出所有可用 Skill（名称与简介）。用户请求专用能力时先调用此工具。"""
    skills = scan_skills()
    if not skills:
        return "当前未配置 Skill 目录或未发现 SKILL.md。"
    lines = [f"共 {len(skills)} 个 Skill："]
    for item in skills:
        runnable = "可执行" if can_run_skill(item["name"]) else "仅文档"
        lines.append(f"- {item['name']}（{runnable}）：{item.get('desc') or '无描述'}")
    return "\n".join(lines)


@tool
def get_skill_details(skill_name: str) -> str:
    """获取指定 Skill 的 SKILL.md 全文，了解用法后再决定是否 run_skill。

    Args:
        skill_name: Skill 名称（不含斜杠前缀）
    """
    name = (skill_name or "").lstrip("/").strip()
    if not name:
        return "请提供 Skill 名称。"
    prompt = load_skill_prompt(name)
    if not prompt:
        return f"未找到 Skill：{name}。可先调用 list_skills 查看可用列表。"
    runnable = "可脚本执行" if can_run_skill(name) else "无可执行脚本，需按文档手动处理"
    return f"【Skill: {name}】（{runnable}）\n\n{prompt[:8000]}"


@tool
def run_skill_tool(skill_name: str, args: str = "") -> str:
    """执行指定 Skill 的脚本（与斜杠命令等效，Agent 可直接调用）。

    Args:
        skill_name: Skill 名称
        args: 传给 Skill 的参数或自然语言描述
    """
    name = (skill_name or "").lstrip("/").strip()
    if not name:
        return "请提供 Skill 名称。"
    result = run_skill(name, args or "", llm=None)
    if result.ok:
        out = (result.output or "").strip() or "（无输出）"
        cmd = f"\n命令：{result.command}" if result.command else ""
        return f"Skill「{name}」执行成功。{cmd}\n\n{out[:6000]}"
    if result.fallback_agent:
        prompt = load_skill_prompt(name)
        hint = prompt[:2000] if prompt else ""
        return (
            f"Skill「{name}」无法自动执行：{result.error}\n"
            f"请参考 SKILL.md 手动处理：\n{hint}"
        )
    return f"Skill「{name}」执行失败：{result.error or '未知错误'}"


@tool
def create_skill(
    name: str,
    description: str,
    instructions: str,
    script_body: str = "",
) -> str:
    """从经验创建新 Skill（写入 data/workspace/skills/）。复杂流程解决后可调用以固化能力。

    Args:
        name: Skill 名称（字母/数字/连字符）
        description: 简短描述（作为 SKILL.md 标题）
        instructions: 详细步骤说明（Markdown）
        script_body: 可选 Python 脚本内容，写入 scripts/main.py
    """
    try:
        root, _ = create_skill_files(
            name,
            description,
            instructions,
            script_body=script_body,
        )
    except ValueError as exc:
        return str(exc)
    slug = root.name
    return f"已创建 Skill「{slug}」于 {root}。可用 list_skills / run_skill_tool / /{slug} 调用。"


@tool
def improve_skill(skill_name: str, addition: str, mode: str = "append") -> str:
    """将新学到的步骤追加到已有 Skill（学习闭环）。

    Args:
        skill_name: 已有 Skill 名称
        addition: 要追加的 Markdown 说明
        mode: append 或 replace
    """
    try:
        root = update_skill_instructions(skill_name, addition, mode=mode)
    except ValueError as exc:
        return str(exc)
    return f"已更新 Skill「{skill_name}」：{root / 'SKILL.md'}"


SKILL_TOOLS = [list_skills, get_skill_details, run_skill_tool, create_skill, improve_skill]
