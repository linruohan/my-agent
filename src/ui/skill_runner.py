"""兼容层：请使用 src.ui.skill.runner。"""
from src.ui.skill.runner import (
    SkillRunResult,
    can_run_skill,
    run_skill,
    CliParam,
    CliSpec,
    _build_argv,
    _collect_free_values,
    _find_entry_script,
    _parse_cli_spec_from_skill,
    _parse_natural_hints,
    _resolve_cli_spec,
)

__all__ = [
    "CliParam",
    "CliSpec",
    "SkillRunResult",
    "_build_argv",
    "_collect_free_values",
    "_find_entry_script",
    "_parse_cli_spec_from_skill",
    "_parse_natural_hints",
    "_resolve_cli_spec",
    "can_run_skill",
    "run_skill",
]
