"""Hermes 风格持久记忆：USER.md / MEMORY.md 读写与 system prompt 注入。"""

from __future__ import annotations

from pathlib import Path

from src.infra.config import load_app_config

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

_MAX_USER_CHARS = 3500
_MAX_MEMORY_CHARS = 4500
_MAX_INJECT_CHARS = _MAX_USER_CHARS

# path -> (mtime_ns, size, raw_text)
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


def build_memory_prompt_block() -> str:
    """组装注入 system prompt 的用户画像与 Agent 记忆块。"""
    user_text = read_context_file(user_file_path(), max_chars=_MAX_USER_CHARS, prefer_tail=False)
    memory_text = read_context_file(memory_file_path(), max_chars=_MAX_MEMORY_CHARS, prefer_tail=True)
    parts: list[str] = []
    if user_text:
        parts.append(f"【用户画像 USER.md】\n{user_text}")
    if memory_text:
        parts.append(f"【Agent 记忆 MEMORY.md】\n{memory_text}")
    if not parts:
        return ""
    guidance = (
        "以上为用户长期偏好与 Agent 跨会话记忆。回答时优先遵循用户画像；"
        "学到可复用经验或用户明确要求记住的信息时，调用 update_agent_memory / update_user_profile 写回。"
    )
    return "\n\n".join(parts) + "\n\n" + guidance
