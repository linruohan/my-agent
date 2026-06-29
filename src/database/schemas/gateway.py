"""Gateway 入站/出站消息与会话映射表。"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS gateway_inbound (
    id         TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    chat_id    TEXT NOT NULL,
    text       TEXT NOT NULL,
    meta_json  TEXT,
    status     TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gateway_outbound (
    id         TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    chat_id    TEXT NOT NULL,
    text       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gw_in_status ON gateway_inbound(status, created_at);
CREATE INDEX IF NOT EXISTS idx_gw_out_status ON gateway_outbound(status, created_at);
CREATE TABLE IF NOT EXISTS gateway_chat_sessions (
    gateway_key TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""
