"""统一数据库表结构 DDL（按领域分文件）。"""

from src.database.schemas.conversation_index import SCHEMA as CONVERSATION_INDEX_SCHEMA
from src.database.schemas.cron_jobs import SCHEMA as CRON_JOBS_SCHEMA
from src.database.schemas.db_meta import SCHEMA as DB_META_SCHEMA
from src.database.schemas.gateway import SCHEMA as GATEWAY_SCHEMA
from src.database.schemas.learning_records import SCHEMA as LEARNING_RECORDS_SCHEMA
from src.database.schemas.notes import SCHEMA as NOTES_SCHEMA
from src.database.schemas.search_cache import SCHEMA as SEARCH_CACHE_SCHEMA
from src.database.schemas.sessions import SCHEMA as SESSIONS_SCHEMA
from src.database.schemas.tasks import SCHEMA as TASKS_SCHEMA
from src.database.schemas.timing_events import SCHEMA as TIMING_EVENTS_SCHEMA

ALL_SCHEMAS: tuple[str, ...] = (
    SESSIONS_SCHEMA,
    TASKS_SCHEMA,
    NOTES_SCHEMA,
    SEARCH_CACHE_SCHEMA,
    TIMING_EVENTS_SCHEMA,
    GATEWAY_SCHEMA,
    CRON_JOBS_SCHEMA,
    CONVERSATION_INDEX_SCHEMA,
    LEARNING_RECORDS_SCHEMA,
    DB_META_SCHEMA,
)

__all__ = ["ALL_SCHEMAS"]
