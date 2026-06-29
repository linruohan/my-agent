"""搜索回复缓存表。"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS search_cache (
    cache_key    TEXT PRIMARY KEY,
    search_query TEXT NOT NULL,
    response     TEXT NOT NULL,
    search_ok    INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    hit_count    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS search_cache_user_queries (
    cache_key  TEXT NOT NULL,
    user_query TEXT NOT NULL,
    added_at   TEXT NOT NULL,
    PRIMARY KEY (cache_key, user_query),
    FOREIGN KEY (cache_key) REFERENCES search_cache(cache_key) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_search_cache_expires ON search_cache(expires_at);
"""
