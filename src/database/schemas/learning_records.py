"""学习闭环去重记录表。"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS learning_records (
    fingerprint   TEXT PRIMARY KEY,
    skill_name      TEXT,
    memory_note     TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_learning_created ON learning_records(created_at);
"""
