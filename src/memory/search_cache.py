"""搜索回复缓存：文本近似匹配命中后直接返回历史汇总，跳过工具与 LLM。"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from loguru import logger

from src.infra.config import load_search_config
from src.infra.paths import DATA_DIR

_CACHE_PATH = DATA_DIR / "search_cache.json"
_STRIP_PREFIX = re.compile(
    r"^(搜索|查找|查询|帮我|请|麻烦|search|find|look up)\s*",
    re.IGNORECASE,
)


@dataclass
class SearchCacheEntry:
    user_query: str
    search_query: str
    response: str
    created_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchCacheEntry:
        return cls(
            user_query=str(data.get("user_query", "")),
            search_query=str(data.get("search_query", "")),
            response=str(data.get("response", "")),
            created_at=str(data.get("created_at", "")),
        )


def _normalize_query(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[：:?？!！。，,、；;\"'`]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = _STRIP_PREFIX.sub("", s).strip()
    return s


def text_similarity(a: str, b: str) -> float:
    na, nb = _normalize_query(a), _normalize_query(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ratio = SequenceMatcher(None, na, nb).ratio()
    # 一方包含另一方时给予额外分数（如「python 3.14」⊂「搜索 python 3.14 新特性」）
    if na in nb or nb in na:
        shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
        contain = len(shorter) / max(len(longer), 1)
        ratio = max(ratio, 0.55 + 0.45 * contain)
    return ratio


class SearchCache:
    def __init__(self, path: Path | None = None) -> None:
        cfg = load_search_config().get("cache", {})
        self.enabled = bool(cfg.get("enabled", True))
        self.text_threshold = float(cfg.get("text_similarity_threshold", 0.65))
        self.max_entries = int(cfg.get("max_entries", 100))
        self.path = path or _CACHE_PATH
        self.entries: list[SearchCacheEntry] = []
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            with self._lock:
                self.entries = [SearchCacheEntry.from_dict(item) for item in raw.get("entries", [])]
        except Exception as exc:
            logger.warning("读取搜索缓存失败: {}", exc)
            with self._lock:
                self.entries = []

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            payload = {"entries": [asdict(e) for e in self.entries]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @property
    def entry_count(self) -> int:
        with self._lock:
            return len(self.entries)

    def _best_text_match(self, query: str) -> tuple[float, str | None]:
        best_score = 0.0
        best_response: str | None = None
        with self._lock:
            entries = list(self.entries)
        for entry in entries:
            score = max(
                text_similarity(query, entry.user_query),
                text_similarity(query, entry.search_query),
            )
            if score > best_score:
                best_score = score
                best_response = entry.response
        return best_score, best_response

    def lookup(self, user_query: str) -> str | None:
        """纯文本近似匹配（同步、毫秒级，不加载 Embedding）。"""
        if not self.enabled or not user_query.strip():
            return None
        with self._lock:
            if not self.entries:
                return None
        score, response = self._best_text_match(user_query.strip())
        if response and score >= self.text_threshold:
            logger.info("搜索缓存文本命中 score={:.3f} query={}", score, user_query[:60])
            return response
        return None

    def save(self, user_query: str, search_query: str, response: str) -> None:
        user_query = user_query.strip()
        response = response.strip()
        if not self.enabled or not user_query or not response:
            return

        entry = SearchCacheEntry(
            user_query=user_query,
            search_query=search_query.strip() or user_query,
            response=response,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        norm = _normalize_query(user_query)
        with self._lock:
            self.entries = [e for e in self.entries if _normalize_query(e.user_query) != norm]
            self.entries.append(entry)
            if len(self.entries) > self.max_entries:
                self.entries = self.entries[-self.max_entries :]
        self._persist()
        logger.info("已写入搜索缓存: {}", user_query[:60])

    def save_async(self, user_query: str, search_query: str, response: str) -> None:
        threading.Thread(
            target=self.save,
            args=(user_query, search_query, response),
            daemon=True,
            name="search-cache-save",
        ).start()
