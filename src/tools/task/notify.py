"""任务提醒通知（Windows 使用 win11toast）。"""

from __future__ import annotations

import html
import sys
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from src.tools.task.store import TaskRow

_KIND_META: dict[str, dict[str, str]] = {
    "reminder": {
        "scenario": "reminder",
        "heading": "⏰ 任务提醒",
    },
    "due": {
        "scenario": "alarm",
        "heading": "🔴 任务到期",
    },
}


def _xml_esc(text: str) -> str:
    return html.escape(text or "—", quote=False)


def _fmt_due_short(iso: str | None) -> str:
    if not iso:
        return "未设置"
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.astimezone()
        else:
            dt = dt.astimezone()
        today = datetime.now().astimezone().date()
        if dt.date() == today:
            return dt.strftime("今天 %H:%M")
        if dt.date() == today + timedelta(days=1):
            return dt.strftime("明天 %H:%M")
        return dt.strftime("%Y/%m/%d %H:%M")
    except ValueError:
        return iso[:16]


def build_task_toast_xml(
    *,
    task_title: str,
    owner: str | None,
    due_at: str | None,
    message: str = "",
    kind: str = "reminder",
) -> str:
    """构建含任务名、负责人、截止时间的 Toast XML（Windows 11 样式）。"""
    meta = _KIND_META.get(kind, _KIND_META["reminder"])
    owner_text = _xml_esc(owner or "未指定")
    due_text = _xml_esc(_fmt_due_short(due_at))
    title_text = _xml_esc(task_title or "未命名任务")
    msg = (message or "").strip()
    msg_block = ""
    if msg:
        msg_block = (
            "<group>"
            "<subgroup>"
            '<text hint-style="captionSubtle">📝 备注</text>'
            f'<text hint-style="body">{_xml_esc(msg[:120])}</text>'
            "</subgroup>"
            "</group>"
        )
    return (
        f'<toast scenario="{meta["scenario"]}">'
        "<visual>"
        '<binding template="ToastGeneric">'
        f'<text hint-maxLines="1">{_xml_esc(meta["heading"])}</text>'
        "<group>"
        "<subgroup>"
        '<text hint-style="captionSubtle">📋 任务名</text>'
        f'<text hint-style="subtitle">{title_text}</text>'
        "</subgroup>"
        "</group>"
        "<group>"
        "<subgroup>"
        '<text hint-style="captionSubtle">👤 负责人</text>'
        f'<text hint-style="base">{owner_text}</text>'
        "</subgroup>"
        "<subgroup>"
        '<text hint-style="captionSubtle">⏱ 截止时间</text>'
        f'<text hint-style="subtitle">{due_text}</text>'
        "</subgroup>"
        "</group>"
        f"{msg_block}"
        "</binding>"
        "</visual>"
        "</toast>"
    )


def _format_plain_task_message(
    *,
    task_title: str,
    owner: str | None,
    due_at: str | None,
    message: str = "",
    kind: str = "reminder",
) -> tuple[str, str]:
    meta = _KIND_META.get(kind, _KIND_META["reminder"])
    title = meta["heading"]
    lines = [
        f"📋 任务名：{task_title or '未命名任务'}",
        f"👤 负责人：{owner or '未指定'}",
        f"⏱ 截止时间：{_fmt_due_short(due_at)}",
    ]
    if (message or "").strip():
        lines.append(f"📝 {message.strip()[:120]}")
    return title, "\n".join(lines)


def send_task_toast(
    title: str,
    message: str = "",
    *,
    owner: str | None = None,
    due_at: str | None = None,
    kind: str = "reminder",
) -> bool:
    """发送任务 Toast。提供 owner/due_at 时使用结构化样式。"""
    rich = owner is not None or due_at is not None
    if rich:
        return _send_rich_task_toast(
            task_title=title,
            owner=owner,
            due_at=due_at,
            message=message,
            kind=kind,
        )
    plain_title = (title or "任务提醒").strip()
    plain_msg = (message or "").strip() or "请查看任务详情"
    if sys.platform != "win32":
        logger.debug("非 Windows 平台，跳过 Toast：{} — {}", plain_title, plain_msg)
        return False
    return _send_simple_toast(plain_title, plain_msg)


def notify_task(task: TaskRow, *, kind: str = "reminder") -> bool:
    """根据任务记录发送结构化提醒。"""
    msg = task.content[:200] if task.content else ""
    return send_task_toast(
        task.title,
        msg,
        owner=task.owner,
        due_at=task.due_at,
        kind=kind,
    )


def _send_rich_task_toast(
    *,
    task_title: str,
    owner: str | None,
    due_at: str | None,
    message: str = "",
    kind: str = "reminder",
) -> bool:
    if sys.platform != "win32":
        logger.debug("非 Windows 平台，跳过 Toast：{}", task_title)
        return False
    xml = build_task_toast_xml(
        task_title=task_title,
        owner=owner,
        due_at=due_at,
        message=message,
        kind=kind,
    )
    try:
        from win11toast import notify

        notify(xml=xml, app_id="my-agent")
        return True
    except ImportError:
        logger.warning("win11toast 未安装，回退 PowerShell Toast")
    except Exception as exc:
        logger.warning("win11toast 通知失败: {}", exc)
    plain_title, plain_msg = _format_plain_task_message(
        task_title=task_title,
        owner=owner,
        due_at=due_at,
        message=message,
        kind=kind,
    )
    return _send_powershell_toast(plain_title, plain_msg, kind=kind)


def _send_simple_toast(title: str, message: str) -> bool:
    try:
        from win11toast import notify

        notify(title, message, app_id="my-agent")
        return True
    except ImportError:
        logger.warning("win11toast 未安装，回退 PowerShell Toast")
        return _send_powershell_toast(title, message)
    except Exception as exc:
        logger.warning("win11toast 通知失败: {}", exc)
        return _send_powershell_toast(title, message)


def _send_powershell_toast(title: str, message: str, *, kind: str = "reminder") -> bool:
    try:
        import subprocess

        scenario = _KIND_META.get(kind, _KIND_META["reminder"])["scenario"]
        safe_title = title.replace("'", "''")
        safe_msg = message.replace("'", "''").replace("\n", "&#10;")
        ps = (
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
            "ContentType = WindowsRuntime] | Out-Null; "
            "$t = @'"
            f"<toast scenario='{scenario}'><visual><binding template='ToastGeneric'>"
            f"<text>{safe_title}</text>"
            f"<text>{safe_msg}</text>"
            f"</binding></visual></toast>"
            "'@; "
            "$x = New-Object Windows.Data.Xml.Dom.XmlDocument; $x.LoadXml($t); "
            "$n = [Windows.UI.Notifications.ToastNotification]::new($x); "
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('my-agent').Show($n)"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            check=False,
            capture_output=True,
            timeout=8,
        )
        return True
    except Exception as exc:
        logger.warning("PowerShell Toast 失败: {}", exc)
        return False
