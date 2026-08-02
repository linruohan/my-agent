"""记忆写入代理：extractMemories 后台代理，自动从对话中抽取记忆。"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from src.infra.config import load_app_config
from src.infra.paths import project_config_dir
from src.memory.memory_index import (
    invalidate_memory_entries_cache,
    schedule_write_memory_index,
)

MEMORY_TYPES = ["user", "feedback", "project", "reference"]
_LAST_WRITE_NAME = ".last_write"
_DEFAULT_MIN_INTERVAL_SEC = 60.0

# 测试/Mock 污染内容（如 MagicMock.__str__ 被误写入记忆）
_TEST_ARTIFACT_RE = re.compile(
    r"(?i)(<MagicMock\b|<_?Mock\b|unittest\.mock|name=['\"]analyze_turn|"
    r"id=['\"]\d+['\"]\s*>)"
)

_extract_lock = threading.Lock()
_extract_busy = False
_extract_pending: dict[str, Any] | None = None


def looks_like_test_artifact(text: str) -> bool:
    """识别 MagicMock / unittest.mock 等不应入库的测试噪声。"""
    body = (text or "").strip()
    if not body:
        return False
    return bool(_TEST_ARTIFACT_RE.search(body))


def last_write_path(project_root: Path | None = None) -> Path:
    return project_config_dir(project_root) / "memory" / _LAST_WRITE_NAME


def get_last_memory_write_ts(project_root: Path | None = None) -> float:
    path = last_write_path(project_root)
    if not path.is_file():
        return 0.0
    try:
        return float(path.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        return 0.0


def mark_memory_written(project_root: Path | None = None, ts: float | None = None) -> None:
    path = last_write_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(ts if ts is not None else time.time()), encoding="utf-8")


def memory_extraction_config() -> dict[str, Any]:
    agent = load_app_config().get("agent", {}) or {}
    cfg = agent.get("memory_extraction", {}) or {}
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "min_interval_sec": float(cfg.get("min_interval_sec", _DEFAULT_MIN_INTERVAL_SEC) or _DEFAULT_MIN_INTERVAL_SEC),
        # 可选：专用 provider 名称；空则使用主对话 LLM
        "provider": str(cfg.get("provider") or "").strip(),
        # 忙碌时只保留最新请求，避免与主对话争抢堆积
        "coalesce": bool(cfg.get("coalesce", True)),
    }


@dataclass
class MemoryWriteResult:
    file_name: str
    memory_type: str
    name: str
    description: str


@dataclass
class ExtractMemoriesInput:
    conversation_id: str
    messages: list[dict[str, Any]]
    has_memory_writes_since: float
    current_work_dir: str


@dataclass
class ExtractMemoriesOutput:
    memories_written: list[MemoryWriteResult]
    index_updated: bool


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


def _generate_file_name(memory_type: str, name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        slug = "memory"
    return f"{memory_type}-{slug}.md"


def _format_memory_content(
    memory_type: str,
    name: str,
    description: str,
    content: str,
    tags: list[str],
) -> str:
    now = datetime.now().strftime("%Y-%m-%d")
    frontmatter = {
        "name": name,
        "description": description,
        "type": memory_type,
        "created": now,
        "updated": now,
        "tags": tags,
    }
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            lines.append(f"{key}: {value}")
        else:
            lines.append(f'{key}: "{value}"')
    lines.append("---")
    lines.append("")
    lines.append(content.strip())
    return "\n".join(lines)


def _convert_relative_dates(content: str) -> str:
    today = datetime.now()
    patterns = [
        (r"\b今天\b", today.strftime("%Y-%m-%d")),
        (r"\b昨天\b", (today.replace(day=today.day - 1)).strftime("%Y-%m-%d")),
    ]
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)
    return content


def _extract_memories_from_messages(
    llm: BaseChatModel,
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    user_messages = []
    assistant_messages = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            user_messages.append(content)
        elif role == "assistant":
            assistant_messages.append(content)

    user_text = "\n".join(user_messages[-5:])[:1500]
    assistant_text = "\n".join(assistant_messages[-5:])[:2000]

    prompt = f"""分析以下对话，提取值得长期记住的信息。只返回 JSON：
{{
  "memories": [
    {{
      "type": "user|feedback|project|reference",
      "name": "简短名称（英文）",
      "description": "一句话描述",
      "content": "详细内容，feedback和project类型必须包含 Why 和 How to apply",
      "tags": ["tag1", "tag2"]
    }}
  ]
}}

类型说明：
- user: 用户角色、偏好、知识背景
- feedback: 用户对工作方式的纠正或确认，必须包含 Why 和 How to apply
- project: 项目进展、目标、截止日期，必须包含 Why 和 How to apply
- reference: 外部系统的指针

不要存储：代码模式、架构、文件路径、项目结构、Git历史、调试方案。
每条记忆必须简短、精确。

用户消息：{user_text}
助手消息：{assistant_text}
"""

    try:
        msg = llm.invoke(
            [
                SystemMessage(content="你是记忆提取器，只输出 JSON。"),
                HumanMessage(content=prompt),
            ]
        )
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        result = _parse_json(content)
        return result.get("memories", [])
    except Exception:
        logger.exception("记忆提取 LLM 调用失败")
        return []


def _validate_memory_content(
    memory_type: str,
    name: str,
    description: str,
    content: str,
) -> tuple[bool, list[str]]:
    """校验记忆内容格式是否符合规范。"""
    errors = []

    if memory_type not in MEMORY_TYPES:
        errors.append(f"无效记忆类型: {memory_type}")
        return False, errors

    if name is None or not str(name).strip():
        errors.append("name 不能为空")
    if description is None or not str(description).strip():
        errors.append("description 不能为空")
    if content is None or not str(content).strip():
        errors.append("content 不能为空")

    if memory_type in ["feedback", "project"]:
        content_str = str(content).lower()
        if "**why:**" not in content_str and "why:" not in content_str:
            errors.append(f"{memory_type} 类型记忆必须包含 Why 部分")
        if "**how to apply:**" not in content_str and "how to apply:" not in content_str:
            errors.append(f"{memory_type} 类型记忆必须包含 How to apply 部分")

    return len(errors) == 0, errors


def _write_memory_file(
    memory_type: str,
    name: str,
    description: str,
    content: str,
    tags: list[str],
    project_root: Path | None = None,
) -> MemoryWriteResult | None:
    if memory_type not in MEMORY_TYPES:
        logger.warning(f"无效记忆类型: {memory_type}")
        return None

    if looks_like_test_artifact(name) or looks_like_test_artifact(description) or looks_like_test_artifact(content):
        logger.warning("[memory] 拒绝写入疑似测试/Mock 噪声: {}", str(name or content)[:120])
        return None

    valid, errors = _validate_memory_content(memory_type, name, description, content)
    if not valid:
        logger.warning(f"记忆格式校验失败: {', '.join(errors)}")
        return None

    if memory_type == "project":
        content = _convert_relative_dates(content)

    file_name = _generate_file_name(memory_type, name)
    memory_dir = project_config_dir(project_root) / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    file_path = memory_dir / file_name

    if file_path.is_file():
        existing = file_path.read_text(encoding="utf-8", errors="ignore")
        if content.strip() in existing:
            logger.debug(f"跳过重复记忆: {file_name}")
            return None

    formatted = _format_memory_content(memory_type, name, description, content, tags)
    file_path.write_text(formatted + "\n", encoding="utf-8")
    logger.info("已写入记忆: {}", file_name)
    invalidate_memory_entries_cache(project_root)
    mark_memory_written(project_root)

    return MemoryWriteResult(
        file_name=file_name,
        memory_type=memory_type,
        name=name,
        description=description,
    )


def write_structured_memory_note(
    note: str,
    *,
    memory_type: str = "feedback",
    name: str | None = None,
    description: str | None = None,
    project_root: Path | None = None,
) -> MemoryWriteResult | None:
    """将一句可复用事实写入结构化记忆文件（学习闭环 / update_agent_memory 共用）。"""
    body = (note or "").strip()
    body = re.sub(r"^[-*•]\s*", "", body)
    if not body:
        return None
    if looks_like_test_artifact(body) or looks_like_test_artifact(name or "") or looks_like_test_artifact(description or ""):
        logger.warning("[memory] 拒绝写入疑似测试/Mock 噪声: {}", body[:120])
        return None

    slug_src = name or body[:40]
    mem_name = (name or slug_src).strip() or "learned-note"
    desc = (description or body[:80]).strip()
    content = body
    if memory_type in ("feedback", "project"):
        if "**Why:**" not in content and "Why:" not in content:
            content = (
                f"{body}\n\n"
                f"**Why:** 对话中确认的可复用事实\n\n"
                f"**How to apply:** 后续相关任务优先遵循此约定"
            )

    result = _write_memory_file(
        memory_type=memory_type,
        name=mem_name,
        description=desc,
        content=content,
        tags=["auto-learn"],
        project_root=project_root,
    )
    if result:
        schedule_write_memory_index(project_root)
    return result


def resolve_extraction_llm(fallback: BaseChatModel | None) -> BaseChatModel | None:
    """解析记忆抽取用 LLM：优先配置的专用 provider，否则回退主模型。"""
    cfg = memory_extraction_config()
    provider_name = cfg.get("provider") or ""
    if not provider_name:
        return fallback
    try:
        from src.infra.config import load_merged_providers
        from src.llm.factory import create_llm

        _default, providers = load_merged_providers()
        provider = providers.get(provider_name)
        if not provider:
            logger.warning("[memory] 抽取 provider「{}」不存在，回退主 LLM", provider_name)
            return fallback
        return create_llm(provider)
    except Exception as exc:
        logger.warning("[memory] 创建抽取 LLM 失败，回退主 LLM: {}", exc)
        return fallback


def schedule_memory_extraction(
    *,
    llm: BaseChatModel | None,
    graph: Any,
    thread_id: str,
    config: dict[str, Any],
) -> None:
    """队列化记忆抽取：单 worker、忙碌时 coalesce 最新请求，避免与主对话争抢堆积。"""
    if not llm or not thread_id:
        return
    if not memory_extraction_config().get("enabled", True):
        return

    job = {
        "llm": llm,
        "graph": graph,
        "thread_id": thread_id,
        "config": config,
    }

    global _extract_busy, _extract_pending
    with _extract_lock:
        if _extract_busy:
            if memory_extraction_config().get("coalesce", True):
                _extract_pending = job
                logger.debug("[memory] 抽取忙碌，合并为最新请求 thread={}", thread_id[:8])
            else:
                logger.debug("[memory] 抽取忙碌且 coalesce=false，丢弃请求")
            return
        _extract_busy = True
        pending = job

    def _run_one(payload: dict[str, Any]) -> None:
        extract_llm = resolve_extraction_llm(payload.get("llm"))
        if not extract_llm:
            return
        try:
            snapshot = payload["graph"].get_state(payload["config"])
            messages = snapshot.values.get("messages", [])
            if not messages:
                return

            message_dicts = []
            for msg in messages:
                if isinstance(msg, dict):
                    message_dicts.append(msg)
                elif hasattr(msg, "role") and hasattr(msg, "content"):
                    message_dicts.append({
                        "role": msg.role,
                        "content": str(msg.content),
                    })
                elif hasattr(msg, "type") and hasattr(msg, "content"):
                    role = "assistant" if msg.type in ("ai", "assistant") else msg.type
                    if role == "human":
                        role = "user"
                    message_dicts.append({
                        "role": role,
                        "content": str(msg.content),
                    })

            input_data = ExtractMemoriesInput(
                conversation_id=payload["thread_id"],
                messages=message_dicts,
                has_memory_writes_since=get_last_memory_write_ts(),
                current_work_dir="",
            )
            result = extract_memories(extract_llm, input_data)
            if result.memories_written:
                logger.info(
                    "[memory] 对话结束后提取到 {} 条记忆",
                    len(result.memories_written),
                )
        except Exception:
            logger.exception("[memory] 后台记忆提取失败")

    def _worker() -> None:
        global _extract_busy, _extract_pending
        current = pending
        while current is not None:
            try:
                _run_one(current)
            finally:
                with _extract_lock:
                    current = _extract_pending
                    _extract_pending = None
                    if current is None:
                        _extract_busy = False

    threading.Thread(target=_worker, daemon=True, name="memory-extract").start()


def extract_memories(
    llm: BaseChatModel,
    input_data: ExtractMemoriesInput,
    *,
    project_root: Path | None = None,
) -> ExtractMemoriesOutput:
    """从对话中提取并写入记忆。"""
    cfg = memory_extraction_config()
    if not cfg["enabled"]:
        return ExtractMemoriesOutput(memories_written=[], index_updated=False)

    last_ts = input_data.has_memory_writes_since
    if last_ts > 0 and (time.time() - last_ts) < cfg["min_interval_sec"]:
        logger.debug(
            "[memory] 距上次写入仅 {:.1f}s，跳过提取（min_interval={}）",
            time.time() - last_ts,
            cfg["min_interval_sec"],
        )
        return ExtractMemoriesOutput(memories_written=[], index_updated=False)

    memories = _extract_memories_from_messages(llm, input_data.messages)
    if not memories:
        return ExtractMemoriesOutput(memories_written=[], index_updated=False)

    written = []
    promoted = []
    for mem in memories:
        result = _write_memory_file(
            memory_type=str(mem.get("type", "user")),
            name=str(mem.get("name", "")),
            description=str(mem.get("description", "")),
            content=str(mem.get("content", "")),
            tags=mem.get("tags", []),
            project_root=project_root,
        )
        if result:
            written.append(result)

            from src.memory.memory_promotion import promote_memory

            promotion_result = promote_memory(
                memory_content=str(mem.get("content", "")),
                memory_name=str(mem.get("name", "")),
                memory_description=str(mem.get("description", "")),
                project_root=project_root,
            )
            if promotion_result and "提权" in promotion_result:
                promoted.append(promotion_result)

    if written:
        schedule_write_memory_index(project_root)

    if promoted:
        logger.info("[memory] {} 条记忆已提权", len(promoted))

    return ExtractMemoriesOutput(
        memories_written=written,
        index_updated=len(written) > 0,
    )