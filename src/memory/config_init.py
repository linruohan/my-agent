"""配置初始化：确保全局和项目配置目录及模板文件存在。"""

from __future__ import annotations

from pathlib import Path

from src.infra.paths import global_config_dir, managed_config_dir, project_config_dir

_DEFAULT_GLOBAL_CLAUDE = """# 全局指导（所有项目生效）

## 用户偏好
- 回复语言：简体中文
- 风格：简洁准确

## 通用规则
- 安全第一：绝不执行危险命令
- 代码质量：遵循最佳实践
"""

_DEFAULT_PROJECT_CLAUDE = """# 项目指导

## 项目概述
- （项目目标、技术栈、架构说明）

## 团队约定
- （代码风格、协作流程、注意事项）
"""

_DEFAULT_USER = """# 用户画像

## 偏好
- 回复语言：简体中文
- 风格：简洁准确

## 项目与环境
- （工作目录、常用工具、项目背景等）
"""

_DEFAULT_MEMORY = """# Agent 记忆索引

## 记忆清单
暂无记忆

## 统计信息
- 最后更新：初始化
- 记忆数量：0

## 重要提醒
- 行为规则（"必须"、"禁止"）已提权到 .my-agent/rules/
- 记忆不是真理，使用前请主动验证
"""

_DEFAULT_GLOBAL_RULES_BEHAVIOR = """---
name: "通用行为规则"
description: "所有项目都应遵守的基本行为准则"
paths: []
priority: "high"
---

## 安全规则
- 禁止执行 rm -rf / 等危险命令
- 禁止访问敏感系统文件
- 涉及 API Key、密码等敏感信息时，使用环境变量

## 代码质量
- 编写清晰的注释
- 遵循项目的编码风格
- 添加适当的错误处理
"""

_DEFAULT_PROJECT_RULES_BEHAVIOR = """---
name: "项目行为规则"
description: "本项目特有的行为准则"
paths: []
priority: "high"
---

## 开发规范
- （项目特有的开发规范）

## 测试要求
- （项目特有的测试要求）
"""

_DEFAULT_SETTINGS = """{
  "model": "",
  "theme": "auto",
  "permissions": {
    "allow": [],
    "deny": []
  },
  "memory": {
    "enabled": true,
    "max_memories": 100,
    "stale_days": 2
  },
  "critical_rules": []
}
"""


def _ensure_file(path: Path, content: str) -> None:
    """确保文件存在，不存在则创建。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_text(content.strip() + "\n", encoding="utf-8")


def init_global_config() -> None:
    """初始化全局配置目录 ~/.my-agent/。"""
    g_dir = global_config_dir()
    g_dir.mkdir(parents=True, exist_ok=True)

    _ensure_file(g_dir / "settings.json", _DEFAULT_SETTINGS)
    _ensure_file(g_dir / "CLAUDE.md", _DEFAULT_GLOBAL_CLAUDE)
    _ensure_file(g_dir / "USER.md", _DEFAULT_USER)
    _ensure_file(g_dir / "MEMORY.md", _DEFAULT_MEMORY)
    _ensure_file(g_dir / "rules" / "behavior.md", _DEFAULT_GLOBAL_RULES_BEHAVIOR)
    _ensure_file(g_dir / "memory" / ".gitkeep", "")


def init_project_config(project_root: Path | None = None) -> None:
    """初始化项目配置目录 .my-agent/。"""
    p_dir = project_config_dir(project_root)
    p_dir.mkdir(parents=True, exist_ok=True)

    _ensure_file(p_dir / "settings.json", _DEFAULT_SETTINGS)
    _ensure_file(p_dir / "settings.local.json", _DEFAULT_SETTINGS)
    _ensure_file(p_dir / "CLAUDE.md", _DEFAULT_PROJECT_CLAUDE)
    _ensure_file(p_dir / "CLAUDE.local.md", _DEFAULT_PROJECT_CLAUDE)
    _ensure_file(p_dir / "USER.md", _DEFAULT_USER)
    _ensure_file(p_dir / "MEMORY.md", _DEFAULT_MEMORY)
    _ensure_file(p_dir / "rules" / "project-behavior.md", _DEFAULT_PROJECT_RULES_BEHAVIOR)
    _ensure_file(p_dir / "rules.local" / ".gitkeep", "")
    _ensure_file(p_dir / "memory" / ".gitkeep", "")
    _ensure_file(p_dir / "memory" / "team" / ".gitkeep", "")


def init_all_configs(project_root: Path | None = None) -> None:
    """初始化所有配置目录。"""
    init_global_config()
    init_project_config(project_root)