"""Hermes 风格持久记忆：USER.md / MEMORY.md 读写与 system prompt 注入。"""

from __future__ import annotations

import re
from pathlib import Path

from src.infra.config import load_app_config
from src.infra.paths import global_config_dir, managed_config_dir, project_config_dir

_DEFAULT_USER = """# 用户画像

## 偏好
- 回复语言：简体中文
- 风格：简洁准确

## 项目与环境
- （工作目录、常用工具、项目背景等）
"""

_DEFAULT_MEMORY = """# Agent 记忆

## 已学会的事项
- （从历史任务中总结的可复用经验与流程）

## 重要事实
- （用户明确要求长期记住的信息）
"""

_DEFAULT_CLAUDE = """# 项目指导

## 项目概述
- （项目目标、技术栈、架构说明）

## 团队约定
- （代码风格、协作流程、注意事项）
"""

_MAX_USER_CHARS = 3500
_MAX_MEMORY_CHARS = 2500
_MAX_CLAUDE_CHARS = 3000
_MAX_INJECT_CHARS = _MAX_USER_CHARS

_file_cache: dict[Path, tuple[int, int, str]] = {}


def invalidate_context_file_cache(path: Path | None = None) -> None:
    """写入后或测试热重载时清除缓存。"""
    if path is None:
        _file_cache.clear()
        return
    _file_cache.pop(Path(path), None)


def _read_file_raw(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        st = path.stat()
    except OSError:
        return ""
    key = (st.st_mtime_ns, st.st_size)
    cached = _file_cache.get(path)
    if cached and cached[0:2] == key:
        return cached[2]
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return ""
    _file_cache[path] = (st.st_mtime_ns, st.st_size, text)
    return text


def workspace_dir() -> Path:
    cfg = load_app_config()
    return Path(cfg["paths"]["workspace"])


def user_file_path() -> Path:
    cfg = load_app_config()
    agent = cfg.get("agent", {}) or {}
    rel = agent.get("user_file", "USER.md")
    return workspace_dir() / rel


def memory_file_path() -> Path:
    cfg = load_app_config()
    agent = cfg.get("agent", {}) or {}
    rel = agent.get("memory_file", "MEMORY.md")
    return workspace_dir() / rel


def ensure_context_files() -> None:
    """确保 workspace 下存在 USER.md / MEMORY.md 模板。"""
    ws = workspace_dir()
    ws.mkdir(parents=True, exist_ok=True)
    for path, template in (
        (user_file_path(), _DEFAULT_USER),
        (memory_file_path(), _DEFAULT_MEMORY),
    ):
        if not path.is_file():
            path.write_text(template.strip() + "\n", encoding="utf-8")


def read_context_file(
    path: Path,
    *,
    max_chars: int = _MAX_INJECT_CHARS,
    prefer_tail: bool = False,
) -> str:
    text = _read_file_raw(path)
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    marker = "\n\n…（已截断）"
    if prefer_tail:
        return "…（前文已截断）\n\n" + text[-(max_chars - 20) :].lstrip()
    return text[: max_chars - len(marker)].rstrip() + marker


def write_context_file(path: Path, content: str, *, mode: str = "replace") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (content or "").strip()
    if not body.endswith("\n"):
        body += "\n"
    if mode == "append" and path.is_file():
        existing = _read_file_raw(path).rstrip()
        if existing:
            body = existing + "\n\n" + body.strip() + "\n"
    path.write_text(body, encoding="utf-8")
    invalidate_context_file_cache(path)


def _resolve_include_path(include_path: str, current_file: Path) -> Path | None:
    """解析 @include 指令中的路径。

    Args:
        include_path: @include 指令中的路径（如 @~/rules/behavior.md 或 @./rules/api.md）
        current_file: 当前正在解析的文件路径

    Returns:
        解析后的绝对路径，若路径不安全或无效则返回 None
    """
    if include_path.startswith("@~/"):
        rel_path = include_path[3:]
        resolved = global_config_dir() / rel_path
    elif include_path.startswith("@./"):
        rel_path = include_path[3:]
        resolved = current_file.parent / rel_path
    else:
        return None

    resolved = resolved.resolve()

    if ".." in resolved.as_posix().split("/") or ".." in resolved.as_posix().split("\\"):
        return None

    try:
        if include_path.startswith("@~/"):
            if not resolved.is_relative_to(global_config_dir()):
                return None
        elif include_path.startswith("@./"):
            project_root = current_file.parent
            while project_root != project_root.parent:
                if (project_root / ".my-agent").is_dir():
                    break
                project_root = project_root.parent
            if not resolved.is_relative_to(project_root):
                return None
    except ValueError:
        return None

    return resolved


def _resolve_include_directives(
    text: str,
    current_file: Path,
    visited: set[Path],
) -> str:
    """递归解析文本中的 @include 指令，处理循环引用。"""
    include_pattern = re.compile(r"^@~?/[^\s\"']+\.md$", re.MULTILINE)
    result = text

    for match in include_pattern.finditer(text):
        include_path = match.group(0)
        resolved = _resolve_include_path(include_path, current_file)

        if not resolved:
            result = result.replace(include_path, f"<!-- @include 路径无效: {include_path} -->")
            continue

        if resolved in visited:
            result = result.replace(include_path, f"<!-- @include 循环引用: {include_path} -->")
            continue

        if not resolved.is_file():
            result = result.replace(include_path, f"<!-- @include 文件不存在: {include_path} -->")
            continue

        visited.add(resolved)
        included_content = _read_file_raw(resolved)
        included_content = _resolve_include_directives(included_content, resolved, visited)
        visited.remove(resolved)

        result = result.replace(include_path, included_content)

    return result


def _find_project_root(start_dir: Path) -> Path | None:
    """从指定目录向上查找项目根目录（包含 .my-agent 的目录）。"""
    current = start_dir.resolve()
    while current != current.parent:
        if (current / ".my-agent").is_dir():
            return current
        current = current.parent
    return None


def _load_nested_claude_files(current_file: str | None, project_root: Path | None) -> list[str]:
    """加载嵌套级 CLAUDE.md 文件（从当前文件目录向上遍历）。"""
    contents = []
    if not current_file:
        return contents

    file_path = Path(current_file).resolve()
    if not file_path.is_file():
        return contents

    root = project_root or _find_project_root(file_path)
    if not root:
        return contents

    visited = set()
    current_dir = file_path.parent

    while current_dir != root.parent:
        agent_dir = current_dir / ".my-agent"
        if agent_dir.is_dir() and agent_dir not in visited:
            visited.add(agent_dir)
            for fname in ["CLAUDE.md", "CLAUDE.local.md"]:
                fpath = agent_dir / fname
                if fpath.is_file():
                    text = _read_file_raw(fpath)
                    if text:
                        resolved_text = _resolve_include_directives(text, fpath, set())
                        contents.append(resolved_text)
        if current_dir == current_dir.parent:
            break
        current_dir = current_dir.parent

    return contents


def load_all_claude_files(
    project_root: Path | None = None,
    current_file: str | None = None,
) -> list[str]:
    """加载所有层级的 CLAUDE.md 文件，解析 @include 指令。
    
    Args:
        project_root: 项目根目录
        current_file: 当前编辑的文件路径，用于加载嵌套级文件
    """
    contents = []
    visited_paths = set()

    def _add_file(path: Path) -> None:
        if path in visited_paths:
            return
        if path.is_file():
            visited_paths.add(path)
            text = _read_file_raw(path)
            if text:
                resolved_text = _resolve_include_directives(text, path, set())
                contents.append(resolved_text)

    _add_file(managed_config_dir() / "CLAUDE.md")
    _add_file(global_config_dir() / "CLAUDE.md")
    _add_file(project_config_dir(project_root) / "CLAUDE.md")
    _add_file(project_config_dir(project_root) / "CLAUDE.local.md")

    nested_contents = _load_nested_claude_files(current_file, project_root)
    for content in nested_contents:
        contents.append(content)

    return contents


def build_claude_prompt_block(
    project_root: Path | None = None,
    current_file: str | None = None,
) -> str:
    """组装注入 system prompt 的 CLAUDE.md 块。"""
    files = load_all_claude_files(project_root, current_file)
    if not files:
        return ""
    total_chars = 0
    parts = []
    for content in files:
        if total_chars + len(content) > _MAX_CLAUDE_CHARS:
            remaining = _MAX_CLAUDE_CHARS - total_chars - 30
            parts.append(content[:remaining].rstrip() + "\n\n…（已截断）")
            break
        parts.append(content)
        total_chars += len(content)
    return "\n\n---\n\n".join(parts)


def _truncate_text(text: str, max_chars: int, prefer_tail: bool = False) -> str:
    """截断文本到指定长度。"""
    if len(text) <= max_chars:
        return text
    marker = "\n\n…（已截断）"
    if prefer_tail:
        return "…（前文已截断）\n\n" + text[-(max_chars - 20) :].lstrip()
    return text[: max_chars - len(marker)].rstrip() + marker


def read_user_profile_merged(max_chars: int = _MAX_USER_CHARS) -> str:
    """读取合并后的用户画像（全局 + 项目 + 本地）。"""
    user_texts = []
    paths = [
        global_config_dir() / "USER.md",
        project_config_dir() / "USER.md",
        # 兼容旧路径 USER.md.local；规范本地画像放在 CLAUDE.local.md 体系旁的 USER 覆盖
        project_config_dir() / "USER.md.local",
        project_config_dir() / "USER.local.md",
        user_file_path(),
    ]
    for path in paths:
        if path.is_file():
            content = _read_file_raw(path)
            if content:
                user_texts.append(content)
    if not user_texts:
        return ""
    merged = "\n\n---\n\n".join(user_texts)
    return _truncate_text(merged, max_chars)


def build_memory_prompt_block() -> str:
    """组装注入 system prompt 的用户画像与 Agent 记忆块。"""
    from src.memory.memory_index import read_memory_index

    user_text = read_user_profile_merged()

    memory_index = read_memory_index()
    if not memory_index:
        memory_index = read_context_file(memory_file_path(), max_chars=_MAX_MEMORY_CHARS, prefer_tail=True)

    parts: list[str] = []
    if user_text:
        parts.append(f"【用户画像 USER.md】\n{user_text}")
    if memory_index:
        parts.append(f"【Agent 记忆索引 MEMORY.md】\n{memory_index}")
    if not parts:
        return ""
    guidance = (
        "以上为用户长期偏好与 Agent 跨会话记忆。回答时优先遵循用户画像；"
        "记忆索引中列出了可用的记忆文件，需要时可调用工具读取详细内容；"
        "学到可复用经验或用户明确要求记住的信息时，调用 update_agent_memory / update_user_profile 写回。"
    )
    return "\n\n".join(parts) + "\n\n" + guidance