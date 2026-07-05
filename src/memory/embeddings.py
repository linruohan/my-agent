from __future__ import annotations

import os
import threading

from langchain_core.embeddings import Embeddings
from loguru import logger


class FastEmbedEmbeddings(Embeddings):
    """基于 fastembed 的本地 Embedding，无需外部 API。"""

    def __init__(self, model_name: str):
        from fastembed import TextEmbedding

        logger.info("加载本地 Embedding 模型: {}", model_name)
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[float]:
        return [[float(v) for v in vec] for vec in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return [float(v) for v in next(self._model.embed([text]))]


class DummyEmbeddings(Embeddings):
    """当 Embedding 模型加载失败时使用的降级实现。"""

    _warned = False
    _warn_lock = threading.Lock()

    def embed_documents(self, texts: list[str]) -> list[float]:
        self._warn_once()
        return [[0.0] * 384 for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        self._warn_once()
        return [0.0] * 384

    def _warn_once(self) -> None:
        with self._warn_lock:
            if not self._warned:
                self._warned = True
                logger.warning("⚠️ 使用降级 Embedding 实现，知识库搜索功能将不可用")


def create_local_embeddings(model_name: str) -> tuple[Embeddings, bool]:
    """创建本地 Embedding，返回 (embeddings, is_fallback)。"""
    try:
        return FastEmbedEmbeddings(model_name), False
    except Exception:
        logger.exception("Embedding 模型加载失败，将使用降级实现")
        return DummyEmbeddings(), True
