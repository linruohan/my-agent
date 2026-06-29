"""定时任务表。"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS cron_jobs (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    action_type  TEXT NOT NULL,
    action_json  TEXT NOT NULL,
    schedule_json TEXT NOT NULL,
    delivery     TEXT NOT NULL DEFAULT 'toast',
    enabled      INTEGER NOT NULL DEFAULT 1,
    last_run_at  TEXT,
    next_run_at  TEXT,
    last_result  TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cron_next ON cron_jobs(enabled, next_run_at);
"""
