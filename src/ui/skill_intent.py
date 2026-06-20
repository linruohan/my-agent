"""兼容层：请使用 src.ui.skill.intent。"""
from src.ui.skill.intent import *  # noqa: F403
from src.ui.skill.intent import parse_skill_command_with_llm

__all__ = ["parse_skill_command_with_llm"]
