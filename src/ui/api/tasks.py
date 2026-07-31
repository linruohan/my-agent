"""任务看板 API（JSON）。"""

from __future__ import annotations

from typing import Any

from src.tools.task.store import VALID_STATUS, TaskRow
from src.ui.api.base import ApiBase


def _task_to_dict(row: TaskRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "content": row.content,
        "due_at": row.due_at,
        "remind_at": row.remind_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "tags": list(row.tags),
        "status": row.status,
        "owner": row.owner,
        "attachments": list(row.attachments),
    }


class TaskApiMixin(ApiBase):
    """任务 CRUD，供 React 看板消费。"""

    def list_tasks(self, include_done: bool = True) -> dict[str, Any]:
        rows = self._ctrl._task_store.list_all(include_done=bool(include_done))
        return {"ok": True, "tasks": [_task_to_dict(r) for r in rows]}

    def add_task(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        title = str(data.get("title") or "").strip()
        if not title:
            return {"ok": False, "error": "标题不能为空"}
        status = str(data.get("status") or "pending").strip()
        if status not in VALID_STATUS:
            status = "pending"
        owner = data.get("owner")
        if owner is not None:
            owner = str(owner).strip() or None
        tags_raw = data.get("tags")
        tags: list[str] = []
        if isinstance(tags_raw, list):
            tags = [str(t).strip() for t in tags_raw if str(t).strip()]
        elif isinstance(tags_raw, str) and tags_raw.strip():
            tags = [t.strip() for t in tags_raw.replace(",", " ").split() if t.strip()]
        try:
            row = self._ctrl._task_store.add(
                title,
                str(data.get("content") or ""),
                due_at=(str(data["due_at"]).strip() or None) if data.get("due_at") else None,
                tags=tags or None,
                status=status,
                owner=owner,
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "task": _task_to_dict(row)}

    def update_task_status(self, task_id: int, status: str) -> dict[str, Any]:
        status = str(status or "").strip()
        if status not in VALID_STATUS:
            return {"ok": False, "error": f"无效状态：{status}"}
        ok = self._ctrl._task_store.update_status(int(task_id), status)
        if not ok:
            return {"ok": False, "error": "任务不存在或更新失败"}
        row = self._ctrl._task_store.get(int(task_id))
        return {"ok": True, "task": _task_to_dict(row) if row else None}

    def delete_task(self, task_id: int) -> dict[str, Any]:
        ok = self._ctrl._task_store.delete(int(task_id))
        if not ok:
            return {"ok": False, "error": "任务不存在"}
        return {"ok": True}

    def update_task(self, task_id: int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        kwargs: dict[str, Any] = {}
        if "title" in data:
            kwargs["title"] = data.get("title")
        if "content" in data:
            kwargs["content"] = data.get("content")
        if "owner" in data:
            kwargs["owner"] = data.get("owner")
        if "due_at" in data:
            due = data.get("due_at")
            kwargs["due_at"] = (str(due).strip() or None) if due is not None else None
        if "status" in data:
            kwargs["status"] = data.get("status")
        if "tags" in data and isinstance(data.get("tags"), list):
            kwargs["tags"] = [str(t) for t in data["tags"]]
        try:
            ok = self._ctrl._task_store.update(int(task_id), **kwargs)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        if not ok:
            return {"ok": False, "error": "任务不存在或更新失败"}
        row = self._ctrl._task_store.get(int(task_id))
        return {"ok": True, "task": _task_to_dict(row) if row else None}
