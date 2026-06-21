from __future__ import annotations

from unittest.mock import MagicMock, patch

from langchain_core.tools import tool

from src.tools import process_wrap
from src.tools import tool_worker


@tool
def _sample_tool(value: str) -> str:
    """示例工具。"""
    return f"ok:{value}"


def test_tool_process_enabled_default():
    assert tool_worker.tool_process_enabled() is True


def test_invoke_tool_in_process_uses_pool(monkeypatch):
    monkeypatch.setattr(tool_worker, "tool_process_enabled", lambda: True)
    mock_run = MagicMock(return_value="done")
    monkeypatch.setattr(tool_worker, "run_in_process", mock_run)

    result = tool_worker.invoke_tool_in_process("web_search", {"query": "test"})
    assert result == "done"
    mock_run.assert_called_once()
    assert mock_run.call_args.args[0] is tool_worker._tool_invoke_worker


def test_wrap_tools_for_process(monkeypatch):
    monkeypatch.setattr(tool_worker, "tool_process_enabled", lambda: True)
    monkeypatch.setattr("src.tools.process_wrap.should_run_in_process", lambda name: True)
    monkeypatch.setattr(
        tool_worker,
        "invoke_tool_in_process",
        lambda name, args, timeout=None: "wrapped",
    )
    wrapped = process_wrap.wrap_tools_for_process([_sample_tool])[0]
    assert wrapped.invoke({"value": "x"}) == "wrapped"


def test_wrap_tools_skips_light_tools(monkeypatch):
    monkeypatch.setattr(tool_worker, "tool_process_enabled", lambda: True)
    monkeypatch.setattr(
        "src.tools.process_wrap.should_run_in_process",
        lambda name: False,
    )
    tools = process_wrap.wrap_tools_for_process([_sample_tool])
    assert tools[0] is _sample_tool


def test_should_run_in_process_defaults(monkeypatch):
    from src.tools import should_run_in_process

    monkeypatch.setattr("src.tools.tool_worker.tool_process_enabled", lambda: True)
    assert should_run_in_process("web_search") is True
    assert should_run_in_process("list_tasks") is False
