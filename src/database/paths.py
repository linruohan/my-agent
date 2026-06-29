"""统一应用数据库路径。"""

from __future__ import annotations

from pathlib import Path

APP_DB_NAME = "app.db"

# 旧版分散数据库 → 需迁移的表名
LEGACY_DB_TABLES: dict[str, tuple[str, ...]] = {
    "sessions.db": ("sessions", "session_messages"),
    "task.db": ("tasks",),
    "note.db": ("notes",),
    "search_cache.db": ("search_cache", "search_cache_user_queries"),
    "metrics.db": ("timing_events",),
    "gateway.db": ("gateway_inbound", "gateway_outbound", "gateway_chat_sessions"),
    "cron_jobs.db": ("cron_jobs",),
    "conversation_index.db": ("conversation_vectors", "conversation_index_meta"),
    "learning.db": ("learning_records",),
}


def app_db_path(data_dir: Path | None = None) -> Path:
    if data_dir is not None:
        return Path(data_dir) / APP_DB_NAME
    from src.infra.paths import DATA_DIR

    return DATA_DIR / APP_DB_NAME
