"""耗时指标表。"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS timing_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    label       TEXT NOT NULL,
    elapsed_ms  INTEGER NOT NULL,
    fields_json TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_timing_label_time ON timing_events(label, created_at);
"""
