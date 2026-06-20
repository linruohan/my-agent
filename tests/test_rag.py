from __future__ import annotations

from pathlib import Path

from src.memory.rag import ingest_files, search_knowledge_base, set_rag_provider


def test_ingest_and_search_txt(tmp_path, monkeypatch):
    import src.memory.rag as rag_mod

    vector_dir = tmp_path / "vectorstore"
    docs_dir = tmp_path / "knowledge"
    meta_file = vector_dir / "index_meta.json"
    monkeypatch.setattr(rag_mod, "_VECTOR_DIR", vector_dir)
    monkeypatch.setattr(rag_mod, "_DOCS_DIR", docs_dir)
    monkeypatch.setattr(rag_mod, "_INDEX_META", meta_file)

    sample = tmp_path / "note.txt"
    sample.write_text("LangGraph 是一个有状态的 Agent 编排框架。", encoding="utf-8")

    from langchain_core.embeddings import Embeddings

    class FakeEmbeddings(Embeddings):
        def embed_documents(self, texts):
            return [[float(len(t)), 1.0] for t in texts]

        def embed_query(self, text):
            return [float(len(text)), 1.0]

    monkeypatch.setattr(rag_mod, "create_embeddings", lambda provider=None: FakeEmbeddings())
    monkeypatch.setattr(rag_mod, "create_local_embeddings", lambda model_name: FakeEmbeddings())

    file_count, chunk_count = ingest_files([sample])
    assert file_count == 1
    assert chunk_count >= 1

    result = search_knowledge_base("LangGraph 是什么")
    assert "LangGraph" in result
