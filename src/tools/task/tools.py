"""LangChain @tool 装饰器：任务管理工具（task.db）。"""

from __future__ import annotations

from langchain_core.tools import tool

from src.tools.task.commands import format_task_list, format_task_search
from src.tools.task.store import TaskStore


@tool
def add_task(
    title: str,
    content: str = "",
    due_at: str = "",
    remind_at: str = "",
    tags: str = "",
    status: str = "pending",
) -> str:
    """添加一条任务到 task.db（与 /tsk add 相同存储）。

    Args:
        title: 任务标题
        content: 任务详情，可留空
        due_at: 到期时间 ISO 格式，可留空
        remind_at: 提醒时间 ISO 格式，可留空
        tags: 逗号分隔标签，如 work,urgent
        status: pending / done / expired / planned，默认 pending
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    try:
        row = TaskStore().add(
            title,
            content,
            due_at=due_at or None,
            remind_at=remind_at or None,
            tags=tag_list or None,
            status=status or "pending",
        )
    except ValueError as exc:
        return str(exc)
    return f"已添加任务 #{row.id}：{row.title}（{row.status}）"


@tool
def list_tasks(include_done: bool = False) -> str:
    """列出任务；默认仅未完成任务（pending / planned / expired）。

    Args:
        include_done: 是否包含已完成任务
    """
    rows = TaskStore().list_all(include_done=include_done)
    if not rows:
        return "当前没有任务。" if include_done else "暂无未完成任务。"
    if include_done:
        return format_task_list(rows, heading="全部任务：")
    return format_task_list(rows)


@tool
def search_tasks(keyword: str) -> str:
    """按关键词搜索任务标题与内容。

    Args:
        keyword: 搜索词
    """
    kw = (keyword or "").strip()
    if not kw:
        return "请提供搜索关键词。"
    return format_task_search(TaskStore().search(kw), kw)


@tool
def complete_task(task_id: int) -> str:
    """将任务标记为已完成。敏感操作，执行前需用户确认。

    Args:
        task_id: 任务 ID
    """
    store = TaskStore()
    if not store.get(task_id):
        return f"未找到任务 #{task_id}"
    if store.update_status(task_id, "done"):
        return f"任务 #{task_id} 已标记为完成。"
    return f"无法更新任务 #{task_id} 的状态。"


@tool
def delete_task(task_id: int) -> str:
    """删除指定任务。敏感操作，执行前需用户确认。

    Args:
        task_id: 任务 ID
    """
    store = TaskStore()
    if store.delete(task_id):
        return f"已删除任务 #{task_id}"
    return f"未找到任务 #{task_id}"


TASK_TOOLS = [add_task, list_tasks, search_tasks, complete_task, delete_task]
