"""主题文件读取工具：供模型调用，读取和管理主题相关文件。"""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool

from src.infra.paths import global_config_dir, project_config_dir
from src.memory.context_files import _read_file_raw


def _find_topic_file(topic_name: str, project_root: Path | None = None) -> Path | None:
    """查找主题文件。"""
    search_paths = [
        global_config_dir() / "memory" / f"{topic_name}.md",
        global_config_dir() / "memory" / f"user-{topic_name}.md",
        global_config_dir() / "memory" / f"reference-{topic_name}.md",
        project_config_dir(project_root) / "memory" / f"{topic_name}.md",
        project_config_dir(project_root) / "memory" / f"user-{topic_name}.md",
        project_config_dir(project_root) / "memory" / f"feedback-{topic_name}.md",
        project_config_dir(project_root) / "memory" / f"project-{topic_name}.md",
        project_config_dir(project_root) / "memory" / f"reference-{topic_name}.md",
        project_config_dir(project_root) / "memory" / "team" / f"{topic_name}.md",
    ]

    for path in search_paths:
        if path.is_file():
            return path
    return None


@tool
def read_topic(topic_name: str) -> str:
    """读取指定主题的记忆文件内容。

    Args:
        topic_name: 主题名称或记忆文件名（如 user-role、feedback-no-mock、reference-linear）
    """
    file_path = _find_topic_file(topic_name)
    if not file_path:
        return f"未找到主题「{topic_name}」对应的记忆文件。"

    content = _read_file_raw(file_path)
    if content:
        return content
    return f"主题「{topic_name}」的文件为空。"


@tool
def list_topics() -> str:
    """列出所有可用的主题（记忆文件）。"""
    topics = []
    visited = set()

    def _scan_dir(memory_dir: Path) -> None:
        if not memory_dir.is_dir():
            return
        for path in sorted(memory_dir.glob("*.md")):
            if path in visited:
                continue
            visited.add(path)
            topics.append(f"- {path.name}")

    _scan_dir(global_config_dir() / "memory")
    _scan_dir(project_config_dir() / "memory")
    _scan_dir(project_config_dir() / "memory" / "team")

    if not topics:
        return "暂无主题文件。"

    return "可用主题文件：\n" + "\n".join(topics)


@tool
def read_rules(topic_name: str = "") -> str:
    """读取规则目录中的文件。

    Args:
        topic_name: 规则文件名（可选，不指定则列出所有规则）
    """
    if not topic_name:
        rules = []
        visited = set()

        def _scan_rules_dir(rules_dir: Path) -> None:
            if not rules_dir.is_dir():
                return
            for path in sorted(rules_dir.glob("*.md")):
                if path in visited:
                    continue
                visited.add(path)
                rules.append(f"- {path.name}")

        _scan_rules_dir(global_config_dir() / "rules")
        _scan_rules_dir(project_config_dir() / "rules")
        _scan_rules_dir(project_config_dir() / "rules.local")

        if not rules:
            return "暂无规则文件。"
        return "可用规则文件：\n" + "\n".join(rules)

    search_paths = [
        global_config_dir() / "rules" / f"{topic_name}.md",
        global_config_dir() / "rules" / topic_name,
        project_config_dir() / "rules" / f"{topic_name}.md",
        project_config_dir() / "rules" / topic_name,
        project_config_dir() / "rules.local" / f"{topic_name}.md",
        project_config_dir() / "rules.local" / topic_name,
    ]

    for path in search_paths:
        if path.is_file():
            content = _read_file_raw(path)
            if content:
                return content
            return f"规则文件「{topic_name}」为空。"

    return f"未找到规则文件「{topic_name}」。"


TOPIC_TOOLS = [
    read_topic,
    list_topics,
    read_rules,
]