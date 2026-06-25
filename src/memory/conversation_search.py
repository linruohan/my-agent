"""跨会话历史消息检索（关键词 + 语义）。"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

from loguru import logger

from src.infra.config import load_search_config
from src.memory.embeddings import create_local_embeddings
from src.memory.rag import _rag_config
from src.ui.session_store import SessionStore


def conversation_search_config() -> dict[str, Any]:
    cfg = load_search_config().get("conversation_search", {}) or {}
    return {
        "semantic_enabled": bool(cfg.get("semantic_enabled", True)),
        "index_enabled": bool(cfg.get("index_enabled", True)),
        "candidate_pool": int(cfg.get("candidate_pool", 400) or 400),
        "index_search_pool": int(cfg.get("index_search_pool", 2000) or 2000),
        "rebuild_batch_size": int(cfg.get("rebuild_batch_size", 100) or 100),
        "min_keyword_hits": int(cfg.get("min_keyword_hits", 2) or 2),
        "similarity_threshold": float(cfg.get("similarity_threshold", 0.35) or 0.35),
    }


@lru_cache(maxsize=1)
def _embeddings():
    model = _rag_config().get("local_embedding_model", "BAAI/bge-small-zh-v1.5")
    return create_local_embeddings(str(model))


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _format_hits(hits: list[dict[str, Any]], *, label: str) -> str:
    if not hits:
        return ""
    lines = [f"找到 {len(hits)} 条{label}："]
    for item in hits:
        role = "用户" if item["role"] == "user" else "助手"
        score = item.get("score")
        suffix = f"（相关度 {score:.2f}）" if isinstance(score, (int, float)) else ""
        snippet = str(item["text"])[:200].replace("\n", " ")
        lines.append(f"- [{item['session_title']}] {role}{suffix}：{snippet}")
    return "\n".join(lines)


def search_conversations_semantic(
    query: str,
    *,
    limit: int = 10,
    candidate_pool: int | None = None,
    threshold: float | None = None,
    store: SessionStore | None = None,
) -> list[dict[str, Any]]:
    """语义检索历史对话，返回带 score 的命中列表。"""
    cfg = conversation_search_config()
    pool = candidate_pool if candidate_pool is not None else cfg["candidate_pool"]
    min_score = threshold if threshold is not None else cfg["similarity_threshold"]
    q = (query or "").strip()
    if not q:
        return []

    try:
        embedder = _embeddings()
        query_vec = embedder.embed_query(q)
    except Exception:
        logger.exception("对话语义检索 Embedding 失败")
        return []

    if cfg.get("index_enabled", True):
        from src.memory.conversation_index import backfill_conversation_index, shared_conversation_index

        index = shared_conversation_index()
        if index.count() == 0:
            backfill_conversation_index(batch_size=cfg.get("rebuild_batch_size", 100), store=store)
        else:
            backfill_conversation_index(batch_size=min(20, cfg.get("rebuild_batch_size", 100)), store=store)
        hits = index.search(query_vec, limit=limit, threshold=min_score)
        if hits:
            return hits

    session_store = store or SessionStore()
    candidates = session_store.fetch_recent_messages(limit=max(20, pool))
    if not candidates:
        return []

    texts = [str(c["text"])[:1500] for c in candidates]
    try:
        doc_vecs = embedder.embed_documents(texts)
    except Exception:
        logger.exception("对话语义检索 Embedding 失败")
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    for cand, vec in zip(candidates, doc_vecs):
        score = _cosine(query_vec, vec)
        if score >= min_score:
            item = dict(cand)
            item["score"] = round(score, 3)
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[: max(1, limit)]]


def search_past_conversations_merged(
    keyword: str,
    *,
    limit: int = 10,
    mode: str = "auto",
    store: SessionStore | None = None,
) -> str:
    """关键词 / 语义 / 自动混合检索。"""
    kw = (keyword or "").strip()
    if not kw:
        return "请提供搜索关键词。"
    mode = (mode or "auto").strip().lower()
    if mode not in ("auto", "keyword", "semantic"):
        mode = "auto"

    session_store = store or SessionStore()
    cfg = conversation_search_config()

    if mode in ("auto", "keyword"):
        hits = session_store.search_messages(kw, limit=limit)
        if hits and (mode == "keyword" or len(hits) >= cfg["min_keyword_hits"]):
            return _format_hits(hits, label="相关记录")

    if mode in ("auto", "semantic") and cfg["semantic_enabled"]:
        semantic_hits = search_conversations_semantic(
            kw,
            limit=limit,
            store=session_store,
        )
        if semantic_hits:
            return _format_hits(semantic_hits, label="语义相关记录")
        if mode == "semantic":
            return f"未找到与「{kw}」语义相关的历史对话。"

    if mode == "keyword" or not cfg["semantic_enabled"]:
        return f"未找到包含「{kw}」的历史对话。"
    return f"未找到与「{kw}」相关的历史对话。"
