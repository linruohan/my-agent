"""迁移脚本：将旧格式 MEMORY.md 迁移到新的「一记忆一文件」格式。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from src.infra.paths import DATA_DIR, project_config_dir


def _parse_v1_memory(path: Path) -> list[tuple[str, str, str]]:
    """解析旧格式 MEMORY.md。"""
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return []

    memories = []
    current_section = ""

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            current_section = line[3:].strip()
        elif line.startswith("- ") and current_section:
            content = line[2:].strip()
            date_match = re.match(r"^(\d{4}-\d{2}-\d{2})\s*[-：:]\s*(.+)$", content)
            if date_match:
                date_str = date_match.group(1)
                description = date_match.group(2)
            else:
                date_str = datetime.now().strftime("%Y-%m-%d")
                description = content

            memories.append((current_section, date_str, description))
        i += 1

    return memories


def _parse_v1_topics(path: Path) -> list[tuple[str, str]]:
    """解析旧格式主题列表。"""
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return []

    topics = []
    lines = text.split("\n")
    for line in lines:
        if line.startswith("- **"):
            match = re.match(r"- \*\*(.+?)\*\*\s*（(.+?)）\s*：(.+)$", line)
            if match:
                name = match.group(1)
                category = match.group(2)
                description = match.group(3)
                topics.append((name, category))

    return topics


def _generate_file_name(memory_type: str, name: str) -> str:
    """生成文件名。"""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        slug = "memory"
    return f"{memory_type}-{slug}.md"


def _format_memory_content(
    memory_type: str,
    name: str,
    description: str,
    content: str,
    date_str: str,
) -> str:
    """格式化记忆文件内容。"""
    lines = [
        "---",
        f'name: "{name}"',
        f'description: "{description}"',
        f'type: "{memory_type}"',
        f'created: "{date_str}"',
        f'updated: "{date_str}"',
        f'tags: ["{memory_type}"]',
        "---",
        "",
        content.strip(),
    ]
    return "\n".join(lines)


def _migrate_v1_to_v2(old_memory_path: Path, new_memory_dir: Path) -> int:
    """执行迁移。"""
    new_memory_dir.mkdir(parents=True, exist_ok=True)

    v1_memories = _parse_v1_memory(old_memory_path)
    if not v1_memories:
        print("旧格式 MEMORY.md 为空，无需迁移")
        return 0

    migrated = 0
    for section, date_str, content in v1_memories:
        memory_type = "feedback"
        if "用户" in section or "偏好" in section:
            memory_type = "user"
        elif "项目" in section or "进展" in section:
            memory_type = "project"
        elif "引用" in section or "链接" in section:
            memory_type = "reference"

        name = content[:50].strip()
        description = content[:100].strip()

        file_name = _generate_file_name(memory_type, name)
        file_path = new_memory_dir / file_name

        formatted = _format_memory_content(memory_type, name, description, content, date_str)
        file_path.write_text(formatted + "\n", encoding="utf-8")
        migrated += 1

    print(f"已迁移 {migrated} 条记忆到 {new_memory_dir}")

    from src.memory.memory_index import write_memory_index

    write_memory_index()
    print("记忆索引已更新")

    return migrated


def main() -> None:
    """主函数。"""
    old_memory_path = DATA_DIR / "workspace" / "MEMORY.md"

    if not old_memory_path.is_file():
        print("未找到旧格式 MEMORY.md，跳过迁移")
        return

    new_memory_dir = project_config_dir() / "memory"

    backup_path = old_memory_path.with_suffix(".md.bak")
    if backup_path.is_file():
        print("备份文件已存在，跳过备份")
    else:
        import shutil

        shutil.copy2(old_memory_path, backup_path)
        print(f"已备份旧文件到 {backup_path}")

    migrated_count = _migrate_v1_to_v2(old_memory_path, new_memory_dir)

    if migrated_count > 0:
        print(f"迁移完成！共迁移 {migrated_count} 条记忆")
    else:
        print("未迁移任何记忆")


if __name__ == "__main__":
    main()