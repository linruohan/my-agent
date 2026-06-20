from __future__ import annotations

from datetime import datetime


def current_date_context() -> str:
    """返回供 System Prompt 使用的当前日期上下文。"""
    now = datetime.now()
    weekdays = "星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"
    weekday = weekdays[now.weekday()]
    return f"{now.strftime('%Y年%m月%d日')} {weekday}"


def current_year() -> int:
    return datetime.now().year


def search_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
