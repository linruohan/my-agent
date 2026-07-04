from __future__ import annotations

import os
from langchain_core.embeddings import Embeddings
from loguru import logger


class FastEmbedEmbeddings(Embeddings):
    """基于 fastembed 的本地 Embedding，无需外部 API。"""

    def __init__(self, model_name: str):
        from fastembed import TextEmbedding

        logger.info("加载本地 Embedding 模型: {}", model_name)
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[float]:
        return [list(vec) for vec in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return list(next(self._model.embed([text])))


class DummyEmbeddings(Embeddings):
    """当 Embedding 模型加载失败时使用的降级实现。"""

    def embed_documents(self, texts: list[str]) -> list[float]:
        return [[0.0] * 384 for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.0] * 384


def create_local_embeddings(model_name: str) -> Embeddings:
    try:
        return FastEmbedEmbeddings(model_name)
    except Exception:
        logger.exception("Embedding 模型加载失败，将使用降级实现")
        return DummyEmbeddings()
