from fastapi.testclient import TestClient
from langchain_core.documents import Document

import api.app as api_app
from llm.schema import LLMConfigurationError
from rag_chain import RagAnswer, SourceReference
from rag_service import RetrievalResult, VectorStoreStats


def test_health_endpoint():
    client = TestClient(api_app.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "rag-api"}


def test_config_status_handles_invalid_env_llm(monkeypatch):
    monkeypatch.setattr(api_app, "get_enabled_embedding_config", lambda: None)
    monkeypatch.setattr(api_app, "get_enabled_llm_config", lambda: None)

    def fake_load_config_from_env():
        raise LLMConfigurationError("bad env")

    monkeypatch.setattr(api_app, "load_config_from_env", fake_load_config_from_env)
    client = TestClient(api_app.app)

    response = client.get("/config/status")

    assert response.status_code == 200
    body = response.json()
    assert body["embedding_configured"] is False
    assert body["llm_configured"] is False


def test_retrieve_endpoint_returns_scored_chunks(monkeypatch):
    doc = Document(
        page_content="测试片段",
        metadata={
            "filename": "policy.txt",
            "source_id": "policy.txt",
            "chunk_id": "policy.txt::chunk-0",
        },
    )

    def fake_retrieve(query, *, top_k, score_threshold, include_scores):
        assert query == "奖学金"
        assert top_k == 3
        assert score_threshold == 0.2
        assert include_scores is True
        return RetrievalResult(
            query=query,
            results=[doc],
            scored_results=[(doc, 0.88)],
            stats=VectorStoreStats(total_chunks=9, files=["policy.txt"]),
        )

    monkeypatch.setattr(api_app, "retrieve", fake_retrieve)
    client = TestClient(api_app.app)

    response = client.post(
        "/retrieve",
        json={"query": "奖学金", "top_k": 3, "score_threshold": 0.2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "奖学金"
    assert body["total_chunks"] == 9
    assert body["results"][0]["score"] == 0.88
    assert body["results"][0]["metadata"]["chunk_id"] == "policy.txt::chunk-0"


def test_answer_endpoint_returns_sources(monkeypatch):
    retrieval = RetrievalResult(
        query="如何申请？",
        results=[],
        scored_results=[],
        stats=VectorStoreStats(total_chunks=5, files=["guide.txt"]),
    )
    answer = RagAnswer(
        question="如何申请？",
        answer="按流程提交材料。[1]",
        sources=[
            SourceReference(
                index=1,
                filename="guide.txt",
                source_id="guide.txt",
                chunk_id="guide.txt::chunk-0",
                score=0.91,
                excerpt="提交材料",
            )
        ],
        context="[1]\n提交材料",
        retrieval=retrieval,
    )

    def fake_answer_question(query, *, top_k, score_threshold, context_max_chars):
        assert query == "如何申请？"
        assert top_k == 5
        assert score_threshold is None
        assert context_max_chars == 12000
        return answer

    monkeypatch.setattr(api_app, "answer_question", fake_answer_question)
    client = TestClient(api_app.app)

    response = client.post("/answer", json={"query": "如何申请？"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "按流程提交材料。[1]"
    assert body["sources"][0]["filename"] == "guide.txt"
    assert body["total_chunks"] == 5
