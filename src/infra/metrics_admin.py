"""耗时指标斜杠命令（/metrics）。"""

from __future__ import annotations

from pathlib import Path

from src.infra.metrics import export_metrics_csv, flush_metrics, get_metrics_store, metrics_enabled


def format_metrics_stats() -> str:
    if not metrics_enabled():
        return "metrics 已关闭（设置环境变量 AGENT_METRICS=1 开启）。"
    flush_metrics()
    store = get_metrics_store()
    labels = store.labels()
    if not labels:
        return "暂无耗时记录。"
    lines = ["耗时指标（最近记录）：", ""]
    for label in labels:
        summary = store.summarize(label)
        if summary["count"]:
            lines.append(
                f"- {label}: n={summary['count']} avg={summary['avg_ms']}ms p95={summary['p95_ms']}ms"
            )
    return "\n".join(lines)


def handle_metrics_command(args: str) -> str:
    body = (args or "").strip()
    if not metrics_enabled():
        return "metrics 已关闭（设置环境变量 AGENT_METRICS=1 开启）。"
    if not body or body.lower() == "stats":
        return format_metrics_stats()
    parts = body.split(None, 1)
    sub = parts[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""
    if sub == "export":
        try:
            out_path = Path(rest) if rest else None
            count, path = export_metrics_csv(out_path)
            return f"已导出 {count} 条耗时记录到：\n{path}"
        except RuntimeError as exc:
            return str(exc)
        except Exception as exc:
            return f"导出失败：{exc}"
    return "用法：/metrics [stats] | export [路径]"
