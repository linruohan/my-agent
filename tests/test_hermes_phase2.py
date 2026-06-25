from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src.gateway.inbox import GatewayInbox
from src.tools.code.sandbox import execute_code_in_sandbox, reset_code_session
from src.ui.skill.writer import create_skill_files


def test_execute_code_persists_session(tmp_path, monkeypatch):
    monkeypatch.setattr("src.tools.code.sandbox._SESSION_DIR", tmp_path)
    reset_code_session("test")
    out1 = execute_code_in_sandbox("x = 41 + 1\nprint(x)", session_id="test")
    assert "42" in out1
    out2 = execute_code_in_sandbox("print(x * 2)", session_id="test")
    assert "84" in out2


def test_execute_code_blocks_os_import(tmp_path, monkeypatch):
    monkeypatch.setattr("src.tools.code.sandbox._SESSION_DIR", tmp_path)
    out = execute_code_in_sandbox("import os\nprint(os.getcwd())", session_id="t2")
    assert "禁止" in out


def test_create_skill_files(tmp_path, monkeypatch):
    monkeypatch.setattr("src.ui.skill.writer.default_skills_dir", lambda: tmp_path / "skills")
    monkeypatch.setattr(
        "src.ui.skill.writer.get_skill_dirs",
        lambda: [tmp_path / "skills"],
    )
    monkeypatch.setattr("src.ui.skill.writer.resolve_skill", lambda _n: None)
    root, created = create_skill_files(
        "demo-skill",
        "演示 Skill",
        "步骤一\n步骤二",
        script_body='print("hello")',
    )
    assert created
    assert (root / "SKILL.md").is_file()
    assert (root / "scripts" / "main.py").is_file()


def test_gateway_inbox_roundtrip(tmp_path):
    db = tmp_path / "gw.db"
    inbox = GatewayInbox(db)
    msg = inbox.push_inbound("http", "c1", "你好")
    popped = inbox.pop_inbound()
    assert popped and popped.text == "你好"
    inbox.mark_inbound_done(msg.id)
    inbox.push_outbound("http", "c1", "回复")
    pending = inbox.fetch_outbound_pending()
    assert pending and pending[0].text == "回复"
