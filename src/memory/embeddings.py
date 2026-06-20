from __future__ import annotations

from langchain_core.embeddings import Embeddings
from loguru import logger


class FastEmbedEmbeddings(Embeddings):
    """基于 fastembed 的本地 Embedding，无需外部 API。"""

    def __init__(self, model_name: str):
        from fastembed import TextEmbedding

        logger.info("加载本地 Embedding 模型: {}", model_name)
        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [list(vec) for vec in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return list(next(self._model.embed([text])))


def create_local_embeddings(model_name: str) -> Embeddings:
    return FastEmbedEmbeddings(model_name)
