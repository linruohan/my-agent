"""搜索回复缓存：文本近似匹配 + SQLite 持久化。"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from loguru import logger

from src.infra.config import load_search_config
from src.infra.paths import DATA_DIR, PROJECT_ROOT
from src.memory.search_cache_db import CacheRow, SearchCacheStore

_LEGACY_JSON = DATA_DIR / "search_cache.json"
_STRIP_PREFIX = re.compile(
    r"^(搜索|查找|查询|帮我|请|麻烦|search|find|look up)\s*",
    re.IGNORECASE,
)


@dataclass
class SearchCacheEntry:
    """兼容旧测试/调用方。"""

    user_query: str
    search_query: str
    response: str
    created_at: str = ""


def _normalize_query(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[：:?？!！。，,、；;\"'`]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = _STRIP_PREFIX.sub("", s).strip()
    return s


def make_cache_key(search_query: str, user_query: str = "") -> str:
    base = search_query.strip() or user_query.strip()
    return _normalize_query(base)


def text_similarity(a: str, b: str) -> float:
    na, nb = _normalize_query(a), _normalize_query(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ratio = SequenceMatcher(None, na, nb).ratio()
    if na in nb or nb in na:
        shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
        contain = len(shorter) / max(len(longer), 1)
        ratio = max(ratio, 0.55 + 0.45 * contain)
    return ratio


class SearchCache:
    def __init__(self, db_path: Path | None = None) -> None:
        cfg = load_search_config().get("cache", {})
        self.enabled = bool(cfg.get("enabled", True))
        self.text_threshold = float(cfg.get("text_similarity_threshold", 0.65))
        self.min_response_chars = int(cfg.get("min_response_chars", 100))
        self.ttl_days = int(cfg.get("ttl_days", 7))
        self.max_entries = int(cfg.get("max_entries", 100))
        self.max_user_queries = int(cfg.get("max_user_queries_per_entry", 5))
        if db_path is not None:
            self.db_path = db_path
        else:
            rel = cfg.get("db_path", "data/search_cache.db")
            self.db_path = (PROJECT_ROOT / rel).resolve()
        self._store = SearchCacheStore(self.db_path)
        self._lock = threading.Lock()
        self._migrate_legacy()

    def _migrate_legacy(self) -> None:
        if _LEGACY_JSON.is_file():
            from src.memory.search_cache_db import SearchCacheStore

            rows = []
            try:
                import json

                raw = json.loads(_LEGACY_JSON.read_text(encoding="utf-8"))
                rows = raw.get("entries", [])
            except Exception:
                pass
            for item in rows:
                user_q = str(item.get("user_query", "")).strip()
                search_q = str(item.get("search_query", "")).strip() or user_q
                response = str(item.get("response", "")).strip()
                if user_q and search_q and response:
                    self.save(
                        user_q,
                        search_q,
                        response,
                        search_ok=True,
                        finished=True,
                        skip_quality=False,
                    )
            if rows:
                backup = _LEGACY_JSON.with_suffix(".json.bak")
                try:
                    _LEGACY_JSON.rename(backup)
                    logger.info("JSON 缓存已迁移至 {} 并备份", self.db_path.name)
                except Exception as exc:
                    logger.warning("JSON 备份失败: {}", exc)

    @property
    def entry_count(self) -> int:
        return self._store.count()

    @property
    def entries(self) -> list[SearchCacheEntry]:
        """只读视图，供测试/debug。"""
        rows = self._store.list_active()
        result: list[SearchCacheEntry] = []
        for row in rows:
            uq = row.user_queries[0] if row.user_queries else row.search_query
            result.append(
                SearchCacheEntry(
                    user_query=uq,
                    search_query=row.search_query,
                    response=row.response,
                    created_at=row.created_at,
                )
            )
        return result

    def _score_row(self, query: str, row: CacheRow) -> float:
        candidates = [row.cache_key, row.search_query, *row.user_queries]
        return max(text_similarity(query, c) for c in candidates if c)

    def lookup(self, user_query: str) -> str | None:
        if not self.enabled or not user_query.strip():
            return None

        query = user_query.strip()
        self._store.prune_expired()

        best_score = 0.0
        best_row: CacheRow | None = None
        for row in self._store.list_active():
            if not row.search_ok:
                continue
            score = self._score_row(query, row)
            if score > best_score:
                best_score = score
                best_row = row

        if best_row and best_score >= self.text_threshold:
            logger.info(
                "搜索缓存命中 score={:.3f} key={} query={}",
                best_score,
                best_row.cache_key[:40],
                query[:60],
            )
            self._store.record_hit(best_row.cache_key)
            return best_row.response
        return None

    def save(
        self,
        user_query: str,
        search_query: str,
        response: str,
        *,
        search_ok: bool = True,
        finished: bool = True,
        skip_quality: bool = False,
    ) -> None:
        if not self.enabled:
            return
        user_query = user_query.strip()
        search_query = (search_query or user_query).strip()
        response = response.strip()
        if not finished or not user_query or not response:
            return
        if not skip_quality:
            if not search_ok:
                return
            if len(response) < self.min_response_chars:
                logger.debug("缓存跳过：回复过短 ({} < {})", len(response), self.min_response_chars)
                return

        cache_key = make_cache_key(search_query, user_query)
        if not cache_key:
            return

        with self._lock:
            self._store.upsert(
                cache_key=cache_key,
                search_query=search_query,
                response=response,
                user_query=user_query,
                search_ok=search_ok,
                ttl_days=self.ttl_days,
                max_user_queries=self.max_user_queries,
            )
            self._store.prune_expired()
            self._store.prune_overflow(self.max_entries)
        logger.info("已写入搜索缓存 [{}]: {}", cache_key[:40], user_query[:60])

    def save_async(
        self,
        user_query: str,
        search_query: str,
        response: str,
        *,
        search_ok: bool = True,
        finished: bool = True,
    ) -> None:
        threading.Thread(
            target=self.save,
            kwargs={
                "user_query": user_query,
                "search_query": search_query,
                "response": response,
                "search_ok": search_ok,
                "finished": finished,
            },
            daemon=True,
            name="search-cache-save",
        ).start()
