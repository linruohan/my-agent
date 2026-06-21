"""Agent 历史截断与配置缓存测试。"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.history import make_pre_model_hook, trim_messages_for_model
from src.infra.config import invalidate_yaml_cache, load_tools_config


def test_trim_messages_keeps_tail():
    messages = [HumanMessage(content=str(i)) for i in range(10)]
    trimmed = trim_messages_for_model(messages, 4)
    assert len(trimmed) == 4
    assert trimmed[0].content == "6"


def test_trim_messages_noop_when_under_limit():
    messages = [HumanMessage(content="hi")]
    assert trim_messages_for_model(messages, 40) is messages


def test_pre_model_hook_returns_empty_when_no_trim():
    hook = make_pre_model_hook(40)
    assert hook is not None
    state = {"messages": [HumanMessage(content="a")]}
    assert hook(state) == {}


def test_pre_model_hook_trims_state():
    hook = make_pre_model_hook(2)
    messages = [SystemMessage(content="sys"), HumanMessage(content="1"), HumanMessage(content="2")]
    result = hook({"messages": messages})
    assert len(result["messages"]) == 2
    assert result["messages"][0].content == "1"


def test_make_pre_model_hook_disabled_for_zero():
    assert make_pre_model_hook(0) is None


def test_yaml_config_cache(tmp_path, monkeypatch):
    import src.infra.config as cfg_mod

    yaml_path = tmp_path / "tools.yaml"
    yaml_path.write_text("tools:\n  web_search:\n    enabled: true\n", encoding="utf-8")
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", tmp_path)
    invalidate_yaml_cache()

    first = load_tools_config()
    yaml_path.write_text("tools:\n  web_search:\n    enabled: false\n", encoding="utf-8")
    second = load_tools_config()
    assert first["tools"]["web_search"]["enabled"] is True
    assert second["tools"]["web_search"]["enabled"] is False

    yaml_path.write_text("tools:\n  web_search:\n    enabled: true\n", encoding="utf-8")
    third = load_tools_config()
    assert third["tools"]["web_search"]["enabled"] is True

    invalidate_yaml_cache()
