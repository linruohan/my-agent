"""记忆写入代理：extractMemories 后台代理，自动从对话中抽取记忆。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from src.infra.paths import project_config_dir
from src.memory.memory_index import write_memory_index

MEMORY_TYPES = ["user", "feedback", "project", "reference"]


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
    logger.info(f"已写入记忆: {file_name}")

    return MemoryWriteResult(
        file_name=file_name,
        memory_type=memory_type,
        name=name,
        description=description,
    )


def extract_memories(
    llm: BaseChatModel,
    input_data: ExtractMemoriesInput,
) -> ExtractMemoriesOutput:
    """从对话中提取并写入记忆。"""
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
        )
        if result:
            written.append(result)

            from src.memory.memory_promotion import promote_memory

            promotion_result = promote_memory(
                memory_content=str(mem.get("content", "")),
                memory_name=str(mem.get("name", "")),
                memory_description=str(mem.get("description", "")),
            )
            if promotion_result and "提权" in promotion_result:
                promoted.append(promotion_result)

    if written:
        write_memory_index()

    if promoted:
        logger.info(f"[memory] {len(promoted)} 条记忆已提权")

    return ExtractMemoriesOutput(
        memories_written=written,
        index_updated=len(written) > 0,
    )