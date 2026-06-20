from __future__ import annotations

from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    pending_action: dict | None
    task_plan: list[str] | None
    retrieved_docs: list | None
    metadata: dict
