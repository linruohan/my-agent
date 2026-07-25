"""记忆系统综合测试：索引、写入、读取、验证、提权、规则加载、配置初始化。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _setup_iso_memory_env(tmp_path: Path, monkeypatch):
    """设置隔离的记忆系统测试环境。"""
    project_root = tmp_path / "project"
    project_root.mkdir()

    global_dir = tmp_path / "global" / ".my-agent"
    global_dir.mkdir(parents=True)
    project_dir = project_root / ".my-agent"
    project_dir.mkdir(parents=True)
    managed_dir = tmp_path / "managed" / "my-agent"
    managed_dir.mkdir(parents=True)

    import src.infra.paths as paths_mod

    monkeypatch.setattr(paths_mod, "global_config_dir", lambda: global_dir)
    monkeypatch.setattr(paths_mod, "project_config_dir", lambda _=None: project_dir)
    monkeypatch.setattr(paths_mod, "managed_config_dir", lambda: managed_dir)

    import src.memory.memory_index as mi_mod
    import src.memory.memory_writer as mw_mod
    import src.memory.memory_reader as mr_mod
    import src.memory.memory_validator as mv_mod
    import src.memory.memory_promotion as mp_mod
    import src.memory.rules_loader as rl_mod
    import src.memory.config_init as ci_mod
    import src.memory.context_files as cf_mod
    import src.memory.settings_store as ss_mod
    import src.infra.config as config_mod

    for mod in (mi_mod, mw_mod, mr_mod, mv_mod, mp_mod, rl_mod, ci_mod, ss_mod):
        monkeypatch.setattr(mod, "global_config_dir", lambda: global_dir, raising=False)
        monkeypatch.setattr(mod, "project_config_dir", lambda _=None: project_dir, raising=False)
        monkeypatch.setattr(mod, "managed_config_dir", lambda: managed_dir, raising=False)

    monkeypatch.setattr(cf_mod, "global_config_dir", lambda: global_dir)
    monkeypatch.setattr(cf_mod, "project_config_dir", lambda _=None: project_dir)
    monkeypatch.setattr(cf_mod, "managed_config_dir", lambda: managed_dir)
    monkeypatch.setattr(config_mod, "global_config_dir", lambda: global_dir)
    monkeypatch.setattr(config_mod, "project_config_dir", lambda _=None: project_dir)
    monkeypatch.setattr(config_mod, "managed_config_dir", lambda: managed_dir)
    config_mod.invalidate_json_cache()

    def fake_workspace_dir():
        ws = project_root / "workspace"
        ws.mkdir(exist_ok=True)
        return ws

    monkeypatch.setattr(cf_mod, "workspace_dir", fake_workspace_dir)

    return {
        "project_root": project_root,
        "global_dir": global_dir,
        "project_dir": project_dir,
        "managed_dir": managed_dir,
    }


class TestMemoryIndex:
    """记忆索引管理测试。"""

    def test_load_empty_entries(self, tmp_path, monkeypatch):
        """测试空目录下加载记忆条目。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_index import load_all_memory_entries

        entries = load_all_memory_entries()
        assert entries == []

    def test_build_index_with_entries(self, tmp_path, monkeypatch):
        """测试构建记忆索引。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_index import build_memory_index, write_memory_index

        memory_dir = env["project_dir"] / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "feedback-no-mock.md").write_text(
            "---\n"
            'name: "不要用 mock 数据库"\n'
            'description: "集成测试必须连真实数据库"\n'
            'type: "feedback"\n'
            'created: "2026-07-05"\n'
            'updated: "2026-07-05"\n'
            'tags: ["testing", "database"]\n'
            "---\n"
            "\n"
            "集成测试必须连真实数据库，不要用 mock。\n"
            "\n"
            "**Why:** mock 测试不可靠\n"
            "**How to apply:** 所有集成测试\n",
            encoding="utf-8",
        )

        index_text = build_memory_index()
        assert "feedback-no-mock.md" in index_text
        assert "集成测试必须连真实数据库" in index_text

    def test_index_truncation(self, tmp_path, monkeypatch):
        """测试索引双截断保险（行数和字节数）。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_index import build_memory_index

        memory_dir = env["project_dir"] / "memory"
        memory_dir.mkdir(parents=True)

        for i in range(300):
            (memory_dir / f"memory-{i:03d}.md").write_text(
                "---\n"
                f'name: "记忆 {i}"\n'
                f'description: "这是第 {i} 条记忆，用来测试索引截断功能"\n'
                f'type: "user"\n'
                f'created: "2026-07-05"\n'
                f'updated: "2026-07-05"\n'
                f'tags: ["test"]\n'
                "---\n"
                f"\n"
                f"记忆内容 {i}\n",
                encoding="utf-8",
            )

        index_text = build_memory_index()
        lines = index_text.count("\n") + 1
        char_len = len(index_text)
        assert lines <= 200 or char_len <= 2500 or "记忆索引已截断" in index_text

    def test_write_memory_index(self, tmp_path, monkeypatch):
        """测试写入记忆索引文件。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_index import write_memory_index

        memory_dir = env["project_dir"] / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "user-test.md").write_text(
            "---\n"
            'name: "测试用户"\n'
            'description: "测试记忆"\n'
            'type: "user"\n'
            'created: "2026-07-05"\n'
            'updated: "2026-07-05"\n'
            'tags: ["test"]\n'
            "---\n"
            "\n"
            "测试内容\n",
            encoding="utf-8",
        )

        write_memory_index()

        index_path = env["project_dir"] / "MEMORY.md"
        assert index_path.is_file()
        content = index_path.read_text(encoding="utf-8")
        assert "user-test.md" in content


class TestMemoryWriter:
    """记忆写入测试。"""

    def test_validate_memory_content_valid(self, tmp_path, monkeypatch):
        """测试有效的记忆内容通过校验。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_writer import _validate_memory_content

        valid, errors = _validate_memory_content(
            memory_type="user",
            name="测试用户",
            description="测试描述",
            content="测试内容",
        )
        assert valid
        assert errors == []

    def test_validate_memory_content_empty_name(self, tmp_path, monkeypatch):
        """测试名称为空时校验失败。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_writer import _validate_memory_content

        valid, errors = _validate_memory_content(
            memory_type="user",
            name="",
            description="测试描述",
            content="测试内容",
        )
        assert not valid
        assert any("name" in e for e in errors)

    def test_validate_memory_content_feedback_missing_why(self, tmp_path, monkeypatch):
        """测试 feedback 类型缺少 Why 时校验失败。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_writer import _validate_memory_content

        valid, errors = _validate_memory_content(
            memory_type="feedback",
            name="测试反馈",
            description="测试描述",
            content="只有内容，没有 Why",
        )
        assert not valid
        assert any("Why" in e for e in errors)

    def test_validate_memory_content_project_valid(self, tmp_path, monkeypatch):
        """测试 project 类型包含 Why 和 How to apply 时通过校验。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_writer import _validate_memory_content

        valid, errors = _validate_memory_content(
            memory_type="project",
            name="项目测试",
            description="项目描述",
            content="项目内容\n\n**Why:** 因为重要\n\n**How to apply:** 所有项目",
        )
        assert valid
        assert errors == []

    def test_generate_file_name(self, tmp_path, monkeypatch):
        """测试生成记忆文件名。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_writer import _generate_file_name

        fname = _generate_file_name("feedback", "不要用 mock")
        assert fname.startswith("feedback-")
        assert fname.endswith(".md")
        assert "mock" in fname

    def test_write_memory_file(self, tmp_path, monkeypatch):
        """测试写入记忆文件。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_writer import _write_memory_file

        result = _write_memory_file(
            memory_type="user",
            name="测试记忆",
            description="这是一个测试记忆",
            content="测试记忆的详细内容",
            tags=["test", "demo"],
        )

        assert result is not None
        assert result.memory_type == "user"
        assert result.name == "测试记忆"

        memory_file = env["project_dir"] / "memory" / result.file_name
        assert memory_file.is_file()
        content = memory_file.read_text(encoding="utf-8")
        assert "测试记忆" in content
        assert "type: user" in content or 'type: "user"' in content

    def test_write_memory_duplicate_skipped(self, tmp_path, monkeypatch):
        """测试重复记忆跳过写入。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_writer import _write_memory_file

        result1 = _write_memory_file(
            memory_type="user",
            name="重复测试",
            description="测试重复",
            content="重复内容",
            tags=["test"],
        )
        assert result1 is not None

        result2 = _write_memory_file(
            memory_type="user",
            name="重复测试",
            description="测试重复",
            content="重复内容",
            tags=["test"],
        )
        assert result2 is None


class TestMemoryReader:
    """记忆读取测试。"""

    def test_should_filter_by_tool_no_tools(self, tmp_path, monkeypatch):
        """测试没有最近工具时不过滤。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_index import MemoryEntry
        from src.memory.memory_reader import _should_filter_by_tool

        entry = MemoryEntry(
            file_name="test.md",
            name="测试",
            description="测试内容",
            memory_type="reference",
            created="2026-07-05",
            updated="2026-07-05",
            tags=["test"],
            path=Path("/tmp/test.md"),
        )
        assert not _should_filter_by_tool(entry, [])

    def test_should_filter_by_tool_usage_doc(self, tmp_path, monkeypatch):
        """测试工具用法文档被过滤。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_index import MemoryEntry
        from src.memory.memory_reader import _should_filter_by_tool

        entry = MemoryEntry(
            file_name="reference-grep.md",
            name="grep 工具用法",
            description="grep 工具的使用方法详解",
            memory_type="reference",
            created="2026-07-05",
            updated="2026-07-05",
            tags=["grep"],
            path=Path("/tmp/test.md"),
        )
        assert _should_filter_by_tool(entry, ["grep"])

    def test_should_filter_by_tool_warning_kept(self, tmp_path, monkeypatch):
        """测试工具警告类记忆不被过滤。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_index import MemoryEntry
        from src.memory.memory_reader import _should_filter_by_tool

        entry = MemoryEntry(
            file_name="reference-grep-pitfall.md",
            name="grep 常见坑点",
            description="grep 工具使用时的常见警告和注意事项",
            memory_type="reference",
            created="2026-07-05",
            updated="2026-07-05",
            tags=["grep"],
            path=Path("/tmp/test.md"),
        )
        assert not _should_filter_by_tool(entry, ["grep"])

    def test_is_stale_fresh(self, tmp_path, monkeypatch):
        """测试新创建的记忆不过期。"""
        from datetime import datetime

        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_index import MemoryEntry
        from src.memory.memory_reader import _is_stale

        today = datetime.now().strftime("%Y-%m-%d")
        entry = MemoryEntry(
            file_name="test.md",
            name="测试",
            description="测试内容",
            memory_type="user",
            created=today,
            updated=today,
            tags=["test"],
            path=Path("/tmp/test.md"),
        )
        assert not _is_stale(entry)

    def test_conversation_state(self, tmp_path, monkeypatch):
        """测试对话状态管理。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_reader import ConversationState

        state = ConversationState()
        assert len(state.already_surfaced_memories) == 0

        state.add_surfaced(["mem1.md", "mem2.md"])
        assert "mem1.md" in state.already_surfaced_memories
        assert "mem2.md" in state.already_surfaced_memories

        state.clear()
        assert len(state.already_surfaced_memories) == 0


class TestMemoryValidator:
    """记忆验证器测试。"""

    def test_validate_memory_format_valid(self, tmp_path, monkeypatch):
        """测试有效记忆文件格式校验通过。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_validator import validate_memory_format

        test_file = tmp_path / "test-memory.md"
        test_file.write_text(
            "---\n"
            'name: "测试记忆"\n'
            'description: "测试描述"\n'
            'type: "user"\n'
            'created: "2026-07-05"\n'
            'updated: "2026-07-05"\n'
            'tags: ["test"]\n'
            "---\n"
            "\n"
            "测试内容\n",
            encoding="utf-8",
        )

        valid, errors = validate_memory_format(test_file)
        assert valid
        assert errors == []

    def test_validate_memory_format_missing_type(self, tmp_path, monkeypatch):
        """测试缺少 type 字段时校验失败。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_validator import validate_memory_format

        test_file = tmp_path / "test-memory.md"
        test_file.write_text(
            "---\n"
            'name: "测试记忆"\n'
            'description: "测试描述"\n'
            "---\n"
            "\n"
            "测试内容\n",
            encoding="utf-8",
        )

        valid, errors = validate_memory_format(test_file)
        assert not valid
        assert any("type" in e for e in errors)

    def test_validate_memory_format_invalid_date(self, tmp_path, monkeypatch):
        """测试日期格式无效时校验失败。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_validator import validate_memory_format

        test_file = tmp_path / "test-memory.md"
        test_file.write_text(
            "---\n"
            'name: "测试记忆"\n'
            'description: "测试描述"\n'
            'type: "user"\n'
            'created: "not-a-date"\n'
            "---\n"
            "\n"
            "测试内容\n",
            encoding="utf-8",
        )

        valid, errors = validate_memory_format(test_file)
        assert not valid
        assert any("created" in e for e in errors)

    def test_validate_memory_format_feedback_missing_structure(self, tmp_path, monkeypatch):
        """测试 feedback 类型缺少 Why/How 时校验失败。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_validator import validate_memory_format

        test_file = tmp_path / "test-memory.md"
        test_file.write_text(
            "---\n"
            'name: "测试反馈"\n'
            'description: "测试描述"\n'
            'type: "feedback"\n'
            'created: "2026-07-05"\n'
            'updated: "2026-07-05"\n'
            "---\n"
            "\n"
            "只有内容，没有结构\n",
            encoding="utf-8",
        )

        valid, errors = validate_memory_format(test_file)
        assert not valid
        assert any("Why" in e for e in errors)
        assert any("How to apply" in e for e in errors)

    def test_contains_file_path(self, tmp_path, monkeypatch):
        """测试检测文件路径。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_validator import contains_file_path

        paths = contains_file_path("请查看 C:\\Users\\test\\file.py 文件")
        assert len(paths) > 0

    def test_contains_function_name(self, tmp_path, monkeypatch):
        """测试检测函数名。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_validator import contains_function_name

        funcs = contains_function_name("def hello_world(): pass")
        assert "hello_world" in funcs


class TestMemoryPromotion:
    """记忆提权协议测试。"""

    def test_detect_rule_type_background(self, tmp_path, monkeypatch):
        """测试背景知识类型判断。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_promotion import _detect_rule_type

        assert _detect_rule_type("用户喜欢简洁的回复") == "background"

    def test_detect_rule_type_rule(self, tmp_path, monkeypatch):
        """测试规则类型判断。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_promotion import _detect_rule_type

        assert _detect_rule_type("必须使用真实数据库进行测试") == "rule"
        assert _detect_rule_type("不要在代码中使用 mock") == "rule"
        assert _detect_rule_type("禁止直接修改生产数据库") == "rule"

    def test_detect_rule_type_critical(self, tmp_path, monkeypatch):
        """测试严重规则类型判断。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_promotion import _detect_rule_type

        assert _detect_rule_type("绝对不要删除生产数据") == "critical"
        assert _detect_rule_type("永远禁止泄露用户隐私") == "critical"

    def test_promote_memory_background(self, tmp_path, monkeypatch):
        """测试背景知识不提权。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_promotion import promote_memory

        result = promote_memory(
            memory_content="用户喜欢简洁的回复风格",
            memory_name="用户偏好",
            memory_description="用户的回复风格偏好",
        )
        assert "背景知识" in result
        assert "无需提权" in result

    def test_promote_memory_to_rules(self, tmp_path, monkeypatch):
        """测试记忆提权到 rules 目录。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_promotion import promote_memory

        result = promote_memory(
            memory_content="必须使用真实数据库进行集成测试，不要用 mock",
            memory_name="不要用 mock 数据库",
            memory_description="集成测试必须连真实数据库",
        )
        assert "提权" in result

        rules_dir = env["project_dir"] / "rules"
        assert rules_dir.is_dir()
        rule_files = list(rules_dir.glob("*.md"))
        assert len(rule_files) > 0

    def test_promote_critical_writes_settings_local_not_app_yaml(self, tmp_path, monkeypatch):
        """critical 提权只写 settings.local.json，禁止污染 config/app.yaml。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.infra.config import CONFIG_DIR
        from src.memory.memory_promotion import promote_memory

        app_yaml = CONFIG_DIR / "app.yaml"
        before = app_yaml.read_bytes() if app_yaml.is_file() else None

        result = promote_memory(
            memory_content="绝对不要删除生产数据",
            memory_name="禁止删生产",
            memory_description="生产安全",
        )
        assert "settings.local.json" in result

        local = env["project_dir"] / "settings.local.json"
        assert local.is_file()
        data = json.loads(local.read_text(encoding="utf-8"))
        assert any(r.get("name") == "禁止删生产" for r in data.get("critical_rules", []))

        after = app_yaml.read_bytes() if app_yaml.is_file() else None
        assert before == after


class TestRulesLoader:
    """规则加载器测试。"""

    def test_load_empty_rules(self, tmp_path, monkeypatch):
        """测试空目录加载规则。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.rules_loader import load_rules

        rules = load_rules()
        assert rules == []

    def test_load_rules_file(self, tmp_path, monkeypatch):
        """测试加载规则文件。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.rules_loader import load_rules

        rules_dir = env["project_dir"] / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "test-rule.md").write_text(
            "---\n"
            'name: "测试规则"\n'
            'description: "测试用的规则"\n'
            "paths: []\n"
            'priority: "high"\n'
            "---\n"
            "\n"
            "这是一条测试规则\n",
            encoding="utf-8",
        )

        rules = load_rules()
        assert len(rules) == 1
        assert rules[0].name == "测试规则"

    def test_rules_path_matching(self, tmp_path, monkeypatch):
        """测试规则按路径条件加载。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.rules_loader import load_rules

        rules_dir = env["project_dir"] / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "api-rule.md").write_text(
            "---\n"
            'name: "API 规则"\n'
            'description: "API 开发规范"\n'
            'paths: ["src/api/**"]\n'
            'priority: "medium"\n'
            "---\n"
            "\n"
            "API 开发规范内容\n",
            encoding="utf-8",
        )
        (rules_dir / "general-rule.md").write_text(
            "---\n"
            'name: "通用规则"\n'
            'description: "通用规则"\n'
            "paths: []\n"
            'priority: "high"\n'
            "---\n"
            "\n"
            "通用规则内容\n",
            encoding="utf-8",
        )

        all_rules = load_rules(current_file=None)
        assert len(all_rules) == 2

        api_rules = load_rules(current_file="src/api/users.py")
        assert len(api_rules) == 2

        frontend_rules = load_rules(current_file="src/ui/main.py")
        assert len(frontend_rules) == 1
        assert frontend_rules[0].name == "通用规则"

    def test_build_rules_prompt_block(self, tmp_path, monkeypatch):
        """测试构建规则提示块。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.rules_loader import build_rules_prompt_block

        rules_dir = env["project_dir"] / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "test-rule.md").write_text(
            "---\n"
            'name: "测试规则"\n'
            'description: "测试"\n'
            "paths: []\n"
            'priority: "high"\n'
            "---\n"
            "\n"
            "测试规则内容\n",
            encoding="utf-8",
        )

        block = build_rules_prompt_block()
        assert "测试规则" in block
        assert "测试规则内容" in block


class TestConfigInit:
    """配置初始化测试。"""

    def test_init_global_config(self, tmp_path, monkeypatch):
        """测试初始化全局配置目录。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.config_init import init_global_config

        init_global_config()

        g_dir = env["global_dir"]
        assert (g_dir / "settings.json").is_file()
        assert (g_dir / "CLAUDE.md").is_file()
        assert (g_dir / "USER.md").is_file()
        assert (g_dir / "MEMORY.md").is_file()
        assert (g_dir / "rules" / "behavior.md").is_file()
        assert (g_dir / "memory").is_dir()

    def test_init_project_config(self, tmp_path, monkeypatch):
        """测试初始化项目配置目录。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.config_init import init_project_config

        init_project_config()

        p_dir = env["project_dir"]
        assert (p_dir / "settings.json").is_file()
        assert (p_dir / "settings.local.json").is_file()
        assert (p_dir / "CLAUDE.md").is_file()
        assert (p_dir / "CLAUDE.local.md").is_file()
        assert (p_dir / "USER.md").is_file()
        assert (p_dir / "MEMORY.md").is_file()
        assert (p_dir / "rules" / "project-behavior.md").is_file()
        assert (p_dir / "memory").is_dir()
        assert (p_dir / "memory" / "team").is_dir()

    def test_init_idempotent(self, tmp_path, monkeypatch):
        """测试初始化是幂等的，重复调用不覆盖现有文件。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.config_init import init_global_config

        init_global_config()

        user_file = env["global_dir"] / "USER.md"
        original_content = "自定义用户画像内容"
        user_file.write_text(original_content, encoding="utf-8")

        init_global_config()

        assert user_file.read_text(encoding="utf-8") == original_content


class TestContextFilesMultiLevel:
    """上下文文件多层级加载测试。"""

    def test_load_all_claude_files_basic(self, tmp_path, monkeypatch):
        """测试加载基础层级的 CLAUDE.md 文件。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.context_files import load_all_claude_files

        (env["global_dir"] / "CLAUDE.md").write_text("# 全局指导\n全局规则\n", encoding="utf-8")
        (env["project_dir"] / "CLAUDE.md").write_text("# 项目指导\n项目规则\n", encoding="utf-8")

        files = load_all_claude_files()
        assert len(files) >= 2
        assert any("全局指导" in f for f in files)
        assert any("项目指导" in f for f in files)

    def test_load_nested_claude_files(self, tmp_path, monkeypatch):
        """测试加载嵌套级 CLAUDE.md 文件。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.context_files import _load_nested_claude_files

        sub_dir = env["project_root"] / "src" / "api" / ".my-agent"
        sub_dir.mkdir(parents=True)
        (sub_dir / "CLAUDE.md").write_text("# API 子目录指导\n", encoding="utf-8")

        current_file_path = env["project_root"] / "src" / "api" / "users.py"
        current_file_path.parent.mkdir(parents=True, exist_ok=True)
        current_file_path.write_text("print('hello')\n", encoding="utf-8")

        files = _load_nested_claude_files(str(current_file_path), env["project_root"])
        assert len(files) >= 1
        assert any("API 子目录指导" in f for f in files)

    def test_build_claude_prompt_block(self, tmp_path, monkeypatch):
        """测试构建 CLAUDE 提示块。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.context_files import build_claude_prompt_block

        (env["project_dir"] / "CLAUDE.md").write_text("# 项目指导\n项目内容\n", encoding="utf-8")

        block = build_claude_prompt_block()
        assert "项目指导" in block
        assert "项目内容" in block

    def test_read_user_profile_merged(self, tmp_path, monkeypatch):
        """测试读取合并的用户画像。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.context_files import read_user_profile_merged

        (env["global_dir"] / "USER.md").write_text("# 全局用户画像\n全局偏好\n", encoding="utf-8")
        (env["project_dir"] / "USER.md").write_text("# 项目用户画像\n项目偏好\n", encoding="utf-8")

        merged = read_user_profile_merged()
        assert "全局用户画像" in merged
        assert "项目用户画像" in merged

    def test_build_memory_prompt_block(self, tmp_path, monkeypatch):
        """测试构建记忆提示块。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.context_files import build_memory_prompt_block

        (env["global_dir"] / "USER.md").write_text("# 用户画像\n测试用户\n", encoding="utf-8")

        block = build_memory_prompt_block()
        assert "用户画像" in block
        assert "测试用户" in block


class TestConfigMerging:
    """配置分层合并测试。"""

    def test_merge_configs_scalar_override(self, tmp_path, monkeypatch):
        """测试标量类型配置覆盖。"""
        from src.infra.config import _merge_configs

        base = {"model": "gpt-3.5", "theme": "light"}
        overlay = {"theme": "dark"}
        result = _merge_configs(base, overlay)
        assert result["model"] == "gpt-3.5"
        assert result["theme"] == "dark"

    def test_merge_configs_list_merge(self, tmp_path, monkeypatch):
        """测试数组类型配置合并（去重）。"""
        from src.infra.config import _merge_configs

        base = {"permissions": {"allow": ["read", "write"]}}
        overlay = {"permissions": {"allow": ["write", "delete"]}}
        result = _merge_configs(base, overlay)
        assert set(result["permissions"]["allow"]) == {"read", "write", "delete"}

    def test_merge_configs_nested_dict(self, tmp_path, monkeypatch):
        """测试嵌套字典合并。"""
        from src.infra.config import _merge_configs

        base = {"memory": {"enabled": True, "max_memories": 50}}
        overlay = {"memory": {"max_memories": 100, "stale_days": 3}}
        result = _merge_configs(base, overlay)
        assert result["memory"]["enabled"] is True
        assert result["memory"]["max_memories"] == 100
        assert result["memory"]["stale_days"] == 3

    def test_load_merged_settings(self, tmp_path, monkeypatch):
        """测试加载合并后的 settings.json。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)

        import src.infra.config as cfg_mod

        monkeypatch.setattr(cfg_mod, "global_config_dir", lambda: env["global_dir"])
        monkeypatch.setattr(cfg_mod, "project_config_dir", lambda _=None: env["project_dir"])
        monkeypatch.setattr(cfg_mod, "managed_config_dir", lambda: env["managed_dir"])

        from src.infra.config import load_merged_settings

        global_settings = {
            "theme": "light",
            "permissions": {"allow": ["read"]},
        }
        (env["global_dir"] / "settings.json").write_text(
            json.dumps(global_settings, indent=2),
            encoding="utf-8",
        )

        project_settings = {
            "theme": "dark",
            "permissions": {"allow": ["write"]},
        }
        (env["project_dir"] / "settings.json").write_text(
            json.dumps(project_settings, indent=2),
            encoding="utf-8",
        )

        merged = load_merged_settings()
        assert merged["theme"] == "dark"
        assert "read" in merged["permissions"]["allow"]
        assert "write" in merged["permissions"]["allow"]


class TestMemoryIndexEdgeCases:
    """记忆索引边界值与异常测试。"""

    def test_load_entries_invalid_yaml(self, tmp_path, monkeypatch):
        """测试加载格式错误的记忆文件被跳过。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_index import load_all_memory_entries

        memory_dir = env["project_dir"] / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "invalid.yaml").write_text("---\nname:\n", encoding="utf-8")

        entries = load_all_memory_entries()
        assert entries == []

    def test_load_entries_empty_file(self, tmp_path, monkeypatch):
        """测试空文件被跳过。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_index import load_all_memory_entries

        memory_dir = env["project_dir"] / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "empty.md").write_text("", encoding="utf-8")

        entries = load_all_memory_entries()
        assert entries == []

    def test_build_index_empty(self, tmp_path, monkeypatch):
        """测试空记忆目录下构建索引。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_index import build_memory_index

        index_text = build_memory_index()
        assert "记忆清单" in index_text
        assert "暂无记忆" in index_text

    def test_build_index_special_characters(self, tmp_path, monkeypatch):
        """测试包含特殊字符的记忆文件。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_index import build_memory_index

        memory_dir = env["project_dir"] / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "test-special.md").write_text(
            '---\nname: "测试特殊字符: @#$%^&*"\ndescription: "包含特殊字符的描述"\ntype: "user"\ncreated: "2026-07-05"\nupdated: "2026-07-05"\ntags: ["特殊"]\n---\n\n内容包含中文和特殊字符 @#$%^&*\n',
            encoding="utf-8",
        )

        index_text = build_memory_index()
        assert "test-special.md" in index_text


class TestMemoryWriterEdgeCases:
    """记忆写入边界值与异常测试。"""

    @pytest.mark.parametrize(
        "memory_type,name,description,content,tags,should_pass",
        [
            ("user", "a", "b", "c", [], True),
            ("user", "", "b", "c", [], False),
            ("user", "a", "", "c", [], False),
            ("user", "a", "b", "", [], False),
            ("feedback", "a", "b", "**Why:** test\n**How to apply:** test", [], True),
            ("feedback", "a", "b", "只有内容", [], False),
            ("project", "a", "b", "**Why:** test\n**How to apply:** test", [], True),
            ("project", "a", "b", "只有内容", [], False),
            ("reference", "a", "b", "参考内容", [], True),
            ("invalid_type", "a", "b", "c", [], False),
        ],
    )
    def test_validate_memory_content_parametrized(
        self, tmp_path, monkeypatch, memory_type, name, description, content, tags, should_pass
    ):
        """参数组合测试：记忆内容校验。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_writer import _validate_memory_content

        valid, errors = _validate_memory_content(memory_type, name, description, content)
        assert valid == should_pass

    def test_write_memory_file_none_values(self, tmp_path, monkeypatch):
        """测试 None 值作为参数。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_writer import _write_memory_file

        result = _write_memory_file(
            memory_type="user",
            name=None,
            description=None,
            content=None,
            tags=None,
        )
        assert result is None

    def test_write_memory_file_large_content(self, tmp_path, monkeypatch):
        """测试超大内容写入。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_writer import _write_memory_file

        large_content = "x" * 100000
        result = _write_memory_file(
            memory_type="user",
            name="大内容测试",
            description="大内容描述",
            content=large_content,
            tags=["large"],
        )

        assert result is not None
        memory_file = env["project_dir"] / "memory" / result.file_name
        assert memory_file.is_file()
        assert len(memory_file.read_text(encoding="utf-8")) >= 100000

    def test_write_memory_file_special_chars(self, tmp_path, monkeypatch):
        """测试特殊字符文件名。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_writer import _write_memory_file

        result = _write_memory_file(
            memory_type="user",
            name="文件名包含特殊字符 @#$%^&*",
            description="描述",
            content="内容",
            tags=["test"],
        )

        assert result is not None
        memory_file = env["project_dir"] / "memory" / result.file_name
        assert memory_file.is_file()


class TestMemoryReaderEdgeCases:
    """记忆读取边界值与异常测试。"""

    @pytest.mark.parametrize(
        "entry_name,entry_desc,tool_name,expected_filter",
        [
            ("grep 用法", "grep 工具使用方法", "grep", True),
            ("grep 警告", "grep 使用警告", "grep", False),
            ("grep 坑点", "grep 常见问题", "grep", False),
            ("sed 用法", "sed 工具使用方法", "grep", False),
            ("通用参考", "通用参考文档", "grep", False),
        ],
    )
    def test_should_filter_by_tool_parametrized(
        self, tmp_path, monkeypatch, entry_name, entry_desc, tool_name, expected_filter
    ):
        """参数组合测试：工具过滤逻辑。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_index import MemoryEntry
        from src.memory.memory_reader import _should_filter_by_tool

        entry = MemoryEntry(
            file_name=f"reference-{tool_name}.md",
            name=entry_name,
            description=entry_desc,
            memory_type="reference",
            created="2026-07-05",
            updated="2026-07-05",
            tags=[tool_name],
            path=Path("/tmp/test.md"),
        )
        assert _should_filter_by_tool(entry, [tool_name]) == expected_filter

    def test_is_stale_old_date(self, tmp_path, monkeypatch):
        """测试过期记忆判断。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_index import MemoryEntry
        from src.memory.memory_reader import _is_stale

        entry = MemoryEntry(
            file_name="old.md",
            name="旧记忆",
            description="过期的记忆",
            memory_type="user",
            created="2020-01-01",
            updated="2020-01-01",
            tags=["old"],
            path=Path("/tmp/test.md"),
        )
        assert _is_stale(entry)

    def test_conversation_state_max_items(self, tmp_path, monkeypatch):
        """测试对话状态最大条目限制。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_reader import ConversationState

        state = ConversationState()
        for i in range(200):
            state.add_surfaced([f"mem{i}.md"])

        assert len(state.already_surfaced_memories) == 100


class TestMemoryValidatorEdgeCases:
    """记忆验证边界值与异常测试。"""

    @pytest.mark.parametrize(
        "file_content,should_pass",
        [
            ("---\nname: \"test\"\ndescription: \"test\"\ntype: \"user\"\ncreated: \"2026-01-01\"\nupdated: \"2026-01-01\"\n---\ncontent", True),
            ("---\nname: \"test\"\ndescription: \"test\"\ntype: \"user\"\n---\ncontent", False),
            ("---\ntype: \"user\"\n---\ncontent", False),
            ("content without frontmatter", False),
            ("---\nname: \"test\"\ndescription: \"test\"\ntype: \"feedback\"\ncreated: \"2026-01-01\"\nupdated: \"2026-01-01\"\n---\n**Why:** test\n**How to apply:** test", True),
            ("---\nname: \"test\"\ndescription: \"test\"\ntype: \"feedback\"\ncreated: \"2026-01-01\"\nupdated: \"2026-01-01\"\n---\ncontent", False),
        ],
    )
    def test_validate_memory_format_parametrized(self, tmp_path, monkeypatch, file_content, should_pass):
        """参数组合测试：记忆文件格式校验。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_validator import validate_memory_format

        test_file = tmp_path / "test.md"
        test_file.write_text(file_content, encoding="utf-8")

        valid, errors = validate_memory_format(test_file)
        assert valid == should_pass

    def test_validate_memory_format_nonexistent_file(self, tmp_path, monkeypatch):
        """测试验证不存在的文件。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_validator import validate_memory_format

        test_file = tmp_path / "nonexistent.md"
        valid, errors = validate_memory_format(test_file)
        assert not valid

    def test_contains_file_path_empty(self, tmp_path, monkeypatch):
        """测试空字符串检测文件路径。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_validator import contains_file_path

        paths = contains_file_path("")
        assert len(paths) == 0

    def test_contains_function_name_empty(self, tmp_path, monkeypatch):
        """测试空字符串检测函数名。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_validator import contains_function_name

        funcs = contains_function_name("")
        assert len(funcs) == 0


class TestMemoryPromotionEdgeCases:
    """记忆提权边界值与异常测试。"""

    @pytest.mark.parametrize(
        "content,expected_type",
        [
            ("用户喜欢喝茶", "background"),
            ("用户喜欢简洁回复", "background"),
            ("必须使用真实数据库", "rule"),
            ("不要使用 mock", "rule"),
            ("禁止直接修改生产数据", "rule"),
            ("绝对不要删除生产数据", "critical"),
            ("永远禁止泄露用户隐私", "critical"),
            ("应该使用真实数据库", "rule"),
            ("建议不要使用 mock", "rule"),
            ("切勿删除生产数据", "critical"),
        ],
    )
    def test_detect_rule_type_parametrized(self, tmp_path, monkeypatch, content, expected_type):
        """参数组合测试：规则类型检测。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_promotion import _detect_rule_type

        assert _detect_rule_type(content) == expected_type

    def test_promote_memory_empty_content(self, tmp_path, monkeypatch):
        """测试空内容不提权。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_promotion import promote_memory

        result = promote_memory(memory_content="", memory_name="", memory_description="")
        assert "背景知识" in result
        assert "无需提权" in result

    def test_promote_memory_none_values(self, tmp_path, monkeypatch):
        """测试 None 值提权。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_promotion import promote_memory

        result = promote_memory(memory_content=None, memory_name=None, memory_description=None)
        assert result is None or "背景知识" in str(result)


class TestRulesLoaderEdgeCases:
    """规则加载边界值与异常测试。"""

    def test_load_rules_empty_dir(self, tmp_path, monkeypatch):
        """测试空目录加载规则。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.rules_loader import load_rules

        rules = load_rules()
        assert rules == []

    def test_load_rules_invalid_yaml(self, tmp_path, monkeypatch):
        """测试格式错误的规则文件被跳过。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.rules_loader import load_rules

        rules_dir = env["project_dir"] / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "invalid.yaml").write_text("---\nname:\n", encoding="utf-8")

        rules = load_rules()
        assert rules == []

    def test_load_rules_nonexistent_current_file(self, tmp_path, monkeypatch):
        """测试 current_file 为 None 时加载所有规则。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.rules_loader import load_rules

        rules_dir = env["project_dir"] / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "test-rule.md").write_text(
            "---\nname: \"测试\"\ndescription: \"测试\"\npaths: []\npriority: \"high\"\n---\n内容",
            encoding="utf-8",
        )

        rules = load_rules(current_file=None)
        assert len(rules) == 1

    def test_build_rules_prompt_block_empty(self, tmp_path, monkeypatch):
        """测试空规则目录构建提示块。"""
        _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.rules_loader import build_rules_prompt_block

        block = build_rules_prompt_block()
        assert block == ""


class TestConfigMergingEdgeCases:
    """配置合并边界值与异常测试。"""

    def test_merge_configs_empty_base(self, tmp_path, monkeypatch):
        """测试空基础配置合并。"""
        from src.infra.config import _merge_configs

        result = _merge_configs({}, {"theme": "dark"})
        assert result == {"theme": "dark"}

    def test_merge_configs_empty_overlay(self, tmp_path, monkeypatch):
        """测试空覆盖配置合并。"""
        from src.infra.config import _merge_configs

        result = _merge_configs({"theme": "light"}, {})
        assert result == {"theme": "light"}

    def test_merge_configs_both_empty(self, tmp_path, monkeypatch):
        """测试两个空配置合并。"""
        from src.infra.config import _merge_configs

        result = _merge_configs({}, {})
        assert result == {}

    def test_merge_configs_none_values(self, tmp_path, monkeypatch):
        """测试包含 None 值的配置合并。"""
        from src.infra.config import _merge_configs

        base = {"theme": "light", "model": None}
        overlay = {"model": "gpt-4"}
        result = _merge_configs(base, overlay)
        assert result["theme"] == "light"
        assert result["model"] == "gpt-4"

    def test_load_merged_settings_no_files(self, tmp_path, monkeypatch):
        """测试没有 settings.json 文件时加载。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        import src.infra.config as cfg_mod

        monkeypatch.setattr(cfg_mod, "global_config_dir", lambda: env["global_dir"])
        monkeypatch.setattr(cfg_mod, "project_config_dir", lambda _=None: env["project_dir"])

        from src.infra.config import load_merged_settings

        merged = load_merged_settings()
        assert merged == {}

    def test_load_merged_settings_invalid_json(self, tmp_path, monkeypatch):
        """测试无效 JSON 文件被跳过。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        import src.infra.config as cfg_mod

        monkeypatch.setattr(cfg_mod, "global_config_dir", lambda: env["global_dir"])
        monkeypatch.setattr(cfg_mod, "project_config_dir", lambda _=None: env["project_dir"])

        (env["global_dir"] / "settings.json").write_text("invalid json", encoding="utf-8")

        from src.infra.config import load_merged_settings

        merged = load_merged_settings()
        assert merged == {}

    def test_extract_respects_last_write_interval(self, tmp_path, monkeypatch):
        """近期写入后提取应被限流跳过。"""
        import time

        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        from src.memory.memory_writer import (
            ExtractMemoriesInput,
            extract_memories,
            mark_memory_written,
        )

        now = time.time()
        mark_memory_written(ts=now)
        monkeypatch.setattr(
            "src.memory.memory_writer.memory_extraction_config",
            lambda: {"enabled": True, "min_interval_sec": 60.0},
        )

        class DummyLLM:
            def invoke(self, *_a, **_k):
                raise AssertionError("限流时应跳过 LLM")

        out = extract_memories(
            DummyLLM(),
            ExtractMemoriesInput(
                conversation_id="t1",
                messages=[{"role": "user", "content": "hi"}],
                has_memory_writes_since=now,
                current_work_dir="",
            ),
        )
        assert out.memories_written == []
        assert out.index_updated is False
        assert (env["project_dir"] / "memory" / ".last_write").is_file()

    def test_team_memory_flag_gates_entries(self, tmp_path, monkeypatch):
        """team 记忆仅在 feature flag 开启时加载。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        team_dir = env["project_dir"] / "memory" / "team"
        team_dir.mkdir(parents=True)
        (team_dir / "feedback-team.md").write_text(
            '---\nname: "team"\ndescription: "t"\ntype: "feedback"\n'
            'created: "2026-01-01"\nupdated: "2026-01-01"\ntags: []\n---\n\n'
            "**Why:** x\n\n**How to apply:** y\n",
            encoding="utf-8",
        )
        from src.memory.memory_index import load_all_memory_entries

        assert load_all_memory_entries() == []

        (env["project_dir"] / "settings.local.json").write_text(
            json.dumps({"memory": {"team_memory_enabled": True}}),
            encoding="utf-8",
        )
        from src.infra.config import invalidate_json_cache

        invalidate_json_cache()
        entries = load_all_memory_entries()
        assert any(e.file_name == "feedback-team.md" for e in entries)

    def test_injection_includes_verification_prompt(self, tmp_path, monkeypatch):
        """注入块应附带路径/函数主动验证提示。"""
        env = _setup_iso_memory_env(tmp_path, monkeypatch)
        mem_dir = env["project_dir"] / "memory"
        mem_dir.mkdir(parents=True)
        (mem_dir / "reference-path.md").write_text(
            '---\nname: "path"\ndescription: "p"\ntype: "reference"\n'
            'created: "2026-01-01"\nupdated: "2026-01-01"\ntags: []\n---\n\n'
            "重要路径 D:\\\\codehub\\\\my-agent\\\\src\\\\main.py\n",
            encoding="utf-8",
        )
        from src.memory.memory_reader import FoundMemory, build_memory_injection_block

        block = build_memory_injection_block([FoundMemory("reference-path.md", 0.9, "path")])
        assert "使用以下记忆前，请先验证" in block
        assert "文件路径" in block