"""对话语义索引向量表。"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversation_vectors (
    message_id     INTEGER PRIMARY KEY,
    session_id     TEXT NOT NULL,
    session_title  TEXT NOT NULL,
    role           TEXT NOT NULL,
    text           TEXT NOT NULL,
    embedding_json TEXT NOT NULL,
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conv_vec_created ON conversation_vectors(message_id DESC);
CREATE TABLE IF NOT EXISTS conversation_index_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""
