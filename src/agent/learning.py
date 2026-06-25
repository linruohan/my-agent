"""对话后自动学习：从复杂工具链提取 Skill / 记忆。"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from src.infra.config import load_app_config
from src.ui.skill.writer import create_skill_files, update_skill_instructions

from src.agent.learning_dedupe import (
    memory_note_exists,
    shared_ledger,
    skill_instructions_exist,
    turn_fingerprint,
)


def learning_loop_config() -> dict[str, Any]:
    agent = load_app_config().get("agent", {}) or {}
    cfg = agent.get("learning_loop", {}) or {}
    dedupe = cfg.get("dedupe", {}) or {}
    return {
        "enabled": bool(cfg.get("enabled", False)),
        "min_tool_calls": int(cfg.get("min_tool_calls", 3) or 3),
        "auto_create_skill": bool(cfg.get("auto_create_skill", True)),
        "auto_update_memory": bool(cfg.get("auto_update_memory", True)),
        "dedupe_enabled": bool(dedupe.get("enabled", True)),
    }


def _parse_json(raw: str) -> dict[str, Any]:
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


def analyze_turn_for_learning(
    llm: BaseChatModel,
    *,
    user_message: str,
    assistant_message: str,
    tool_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    """LLM 判断是否值得保存为 Skill 或记忆。"""
    tools_text = json.dumps(tool_calls[:12], ensure_ascii=False)[:2000]
    prompt = f"""分析以下 Agent 对话轮次，判断是否包含可复用的工作流程。
只返回 JSON（不要 markdown）：
{{
  "save_skill": true/false,
  "skill_name": "kebab-case 名称",
  "description": "一句话描述",
  "instructions": "Markdown 步骤说明",
  "memory_note": "若无 Skill 但有值得记住的短事实，填写一句；否则空字符串"
}}

规则：
- 至少使用了多个不同工具，且完成了明确任务时，才 save_skill=true
- skill_name 用英文 kebab-case，如 daily-task-summary
- 普通闲聊、简单单次搜索 save_skill=false

用户：{user_message[:800]}
助手：{assistant_message[:1200]}
工具调用：{tools_text}
"""
    try:
        msg = llm.invoke(
            [
                SystemMessage(content="你是 Agent 学习分析器，只输出 JSON。"),
                HumanMessage(content=prompt),
            ]
        )
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        return _parse_json(content)
    except Exception:
        logger.exception("学习分析 LLM 调用失败")
        return {}


def apply_learning(
    analysis: dict[str, Any],
    *,
    auto_create_skill: bool,
    auto_update_memory: bool,
) -> str | None:
    """根据分析结果写入 Skill 或 MEMORY。"""
    parts: list[str] = []

    if auto_create_skill and analysis.get("save_skill"):
        name = str(analysis.get("skill_name") or "").strip()
        desc = str(analysis.get("description") or name).strip()
        instructions = str(analysis.get("instructions") or "").strip()
        if name and instructions:
            if skill_instructions_exist(name, instructions):
                logger.debug("学习闭环跳过重复 Skill 说明：{}", name)
            else:
                try:
                    root, _ = create_skill_files(name, desc, instructions)
                    parts.append(f"已自动创建 Skill「{root.name}」")
                except ValueError as exc:
                    if "已存在" in str(exc):
                        if not skill_instructions_exist(name, instructions):
                            try:
                                update_skill_instructions(name, instructions, mode="append")
                                parts.append(f"已更新 Skill「{name}」")
                            except ValueError:
                                pass
                    else:
                        logger.debug("自动 Skill 跳过: {}", exc)

    note = str(analysis.get("memory_note") or "").strip()
    if auto_update_memory and note:
        if memory_note_exists(note):
            logger.debug("学习闭环跳过重复 MEMORY 条目")
        else:
            from src.tools.memory.tools import update_agent_memory

            update_agent_memory.invoke({"content": f"- {note}", "mode": "append"})
            parts.append("已写入 MEMORY.md")

    return "；".join(parts) if parts else None


def maybe_learn_from_turn(
    llm: BaseChatModel | None,
    *,
    user_message: str,
    assistant_message: str,
    tool_calls: list[dict[str, Any]],
) -> str | None:
    cfg = learning_loop_config()
    if not cfg["enabled"] or not llm:
        return None
    if len(tool_calls) < cfg["min_tool_calls"]:
        return None
    if not (user_message or "").strip() or not (assistant_message or "").strip():
        return None

    fingerprint = turn_fingerprint(user_message, tool_calls)
    ledger = shared_ledger()
    if cfg["dedupe_enabled"] and ledger.has_fingerprint(fingerprint):
        logger.debug("学习闭环跳过重复轮次 fingerprint={}", fingerprint)
        return None

    analysis = analyze_turn_for_learning(
        llm,
        user_message=user_message,
        assistant_message=assistant_message,
        tool_calls=tool_calls,
    )
    if not analysis:
        return None

    skill_name = str(analysis.get("skill_name") or "").strip() if analysis.get("save_skill") else ""
    memory_note = str(analysis.get("memory_note") or "").strip()
    result = apply_learning(
        analysis,
        auto_create_skill=cfg["auto_create_skill"],
        auto_update_memory=cfg["auto_update_memory"],
    )
    if cfg["dedupe_enabled"]:
        ledger.record(fingerprint, skill_name=skill_name, memory_note=memory_note)
    return result
