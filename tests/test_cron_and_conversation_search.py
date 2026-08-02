"""Cron 投递与对话语义检索测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.automation.delivery import (
    deliver_cron_result,
    parse_gateway_delivery,
    resolve_cron_delivery,
)
from src.automation.store import CronJobStore
from src.memory.conversation_search import search_past_conversations_merged
from src.ui.session_store import SessionStore


def test_resolve_cron_delivery_gateway_default(monkeypatch):
    monkeypatch.setattr(
        "src.gateway.config.load_gateway_config",
        lambda: {"cron_default": {"source": "telegram", "chat_id": "99"}},
    )
    assert resolve_cron_delivery("gateway") == "gateway:telegram:99"
    assert resolve_cron_delivery("default") == "gateway:telegram:99"
    assert resolve_cron_delivery("toast") == "toast"


def test_resolve_cron_delivery_gateway_without_default(monkeypatch):
    monkeypatch.setattr(
        "src.gateway.config.load_gateway_config",
        lambda: {"cron_default": {"source": "", "chat_id": ""}},
    )
    assert resolve_cron_delivery("gateway") is None


def test_parse_gateway_delivery():
    assert parse_gateway_delivery("gateway:telegram:123") == ("telegram", "123")
    assert parse_gateway_delivery("gateway:http:client-a") == ("http", "client-a")
    assert parse_gateway_delivery("toast") is None
    assert parse_gateway_delivery("gateway:only") is None


def test_deliver_cron_result_gateway(tmp_path):
    store = CronJobStore(tmp_path / "cron.db")
    job = store.add(
        name="remote ping",
        action_type="notify",
        action={"message": "hello"},
        schedule={"type": "interval", "minutes": 60},
        delivery="gateway:telegram:42",
    )
    gateway = MagicMock()
    deliver_cron_result(job, "任务完成", gateway_deliver=gateway)
    gateway.assert_called_once()
    assert gateway.call_args[0][0] == "telegram"
    assert gateway.call_args[0][1] == "42"
    assert "任务完成" in gateway.call_args[0][2]


def test_deliver_cron_result_session_only(tmp_path):
    store = CronJobStore(tmp_path / "cron2.db")
    job = store.add(
        name="local",
        action_type="notify",
        action={"message": "x"},
        schedule={"type": "interval", "minutes": 1},
        delivery="session",
    )
    session = MagicMock()
    with patch("src.automation.delivery.send_cron_toast") as toast:
        deliver_cron_result(job, "本地结果", session_handler=session)
        toast.assert_not_called()
    session.assert_called_once_with(job, "本地结果")


def test_search_past_conversations_keyword(tmp_path):
    db = tmp_path / "sessions.db"
    store = SessionStore(db_path=db)
    session = store.create_session("测试会话")
    store.append_event(session.id, {"type": "user", "content": "帮我写 Python 脚本"})
    store.append_event(session.id, {"type": "assistant_end", "content": "好的，我来帮你写脚本。"})

    out = search_past_conversations_merged("Python", limit=5, mode="keyword", store=store)
    assert "Python" in out


def test_conversation_index_backfill_and_search(tmp_path, monkeypatch):
    from src.memory.conversation_index import ConversationIndex, backfill_conversation_index

    sessions_db = tmp_path / "sessions.db"
    index_db = tmp_path / "conv_index.db"
    store = SessionStore(db_path=sessions_db)
    index = ConversationIndex(db_path=index_db)
    session = store.create_session("索引测试")
    store.append_event(session.id, {"type": "user", "content": "讨论向量数据库选型"})
    store.append_event(session.id, {"type": "assistant_end", "content": "推荐 FAISS 本地索引。"})

    class FakeEmbeddings:
        def embed_documents(self, texts: list[str]):
            out = []
            for t in texts:
                if "向量" in t or "FAISS" in t:
                    out.append([1.0, 0.0, 0.0])
                else:
                    out.append([0.0, 1.0, 0.0])
            return out

        def embed_query(self, text: str):
            if "embedding" in text or "向量" in text:
                return [1.0, 0.0, 0.0]
            return [0.0, 1.0, 0.0]

    monkeypatch.setattr("src.memory.conversation_index._embeddings", lambda: FakeEmbeddings())
    monkeypatch.setattr("src.memory.conversation_search._embeddings", lambda: FakeEmbeddings())
    monkeypatch.setattr(
        "src.memory.conversation_index.shared_conversation_index",
        lambda: index,
    )

    added = backfill_conversation_index(batch_size=10, store=store, index=index)
    assert added >= 1
    assert index.count() >= 1

    hits = index.search([1.0, 0.0, 0.0], limit=5, threshold=0.5)
    assert hits and any("FAISS" in h["text"] or "向量" in h["text"] for h in hits)

    out = search_past_conversations_merged("向量 embedding", limit=3, mode="semantic", store=store)
    assert "FAISS" in out or "向量" in out


def test_fetch_messages_for_index_skips_indexed_same_db(tmp_path, monkeypatch):
    from src.memory.conversation_index import ConversationIndex, backfill_conversation_index

    db = tmp_path / "shared.db"
    store = SessionStore(db_path=db)
    index = ConversationIndex(db_path=db)
    session = store.create_session("去重")
    store.append_event(session.id, {"type": "user", "content": "第一条待索引"})
    store.append_event(session.id, {"type": "assistant_end", "content": "第二条待索引"})

    class FakeEmbeddings:
        def embed_documents(self, texts: list[str]):
            return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr("src.memory.conversation_index._embeddings", lambda: FakeEmbeddings())
    added = backfill_conversation_index(batch_size=10, store=store, index=index)
    assert added == 2
    assert store.fetch_messages_for_index(limit=10) == []
    added_again = backfill_conversation_index(batch_size=10, store=store, index=index)
    assert added_again == 0


def test_search_past_conversations_semantic_mock(tmp_path):
    db = tmp_path / "sessions2.db"
    store = SessionStore(db_path=db)
    session = store.create_session("语义测试")
    store.append_event(session.id, {"type": "user", "content": "上次讨论的机器学习项目进度"})
    store.append_event(session.id, {"type": "assistant_end", "content": "项目已完成数据清洗阶段。"})

    class FakeEmbeddings:
        def embed_query(self, text: str):
            if "深度学习" in text:
                return [1.0, 0.0]
            return [0.0, 1.0]

        def embed_documents(self, texts: list[str]):
            out = []
            for t in texts:
                if "机器学习" in t or "数据清洗" in t:
                    out.append([1.0, 0.0])
                else:
                    out.append([0.0, 1.0])
            return out

    with patch("src.memory.conversation_search._embeddings", return_value=FakeEmbeddings()):
        with patch(
            "src.memory.conversation_search.conversation_search_config",
            return_value={
                "semantic_enabled": True,
                "index_enabled": False,
                "candidate_pool": 400,
                "index_search_pool": 2000,
                "rebuild_batch_size": 100,
                "min_keyword_hits": 2,
                "similarity_threshold": 0.35,
            },
        ):
            out = search_past_conversations_merged(
                "深度学习训练",
                limit=5,
                mode="semantic",
                store=store,
            )
    assert "语义相关" in out or "数据清洗" in out
