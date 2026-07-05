"""FastAPI application for the RAG pipeline."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import (
    AnswerRequest,
    AnswerResponse,
    ConfigStatusResponse,
    HealthResponse,
    IndexRequest,
    IndexResponse,
    RetrievedChunk,
    RetrievalRequest,
    RetrievalResponse,
    SourceReferenceResponse,
    VectorStatsResponse,
)
from embedding import init_db
from embedding.crud import get_enabled_config as get_enabled_embedding_config
from llm.crud import get_enabled_config as get_enabled_llm_config
from llm.env import load_config_from_env
from llm.schema import LLMConfigurationError
from rag_chain import answer_question
from rag_service import (
    ConfigurationError,
    get_embeddings_or_raise,
    get_vector_store_stats,
    index_documents,
    retrieve,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="RAG Service API",
    version="0.1.0",
    description="FastAPI interface for document indexing, semantic retrieval, and RAG answers.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _safe_http_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=message)


def _metadata_to_dict(metadata: dict) -> dict:
    return {str(key): value for key, value in metadata.items()}


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="rag-api")


@app.get("/config/status", response_model=ConfigStatusResponse)
def config_status() -> ConfigStatusResponse:
    init_db()
    embedding_config = get_enabled_embedding_config()
    llm_config = get_enabled_llm_config()
    llm_source = "database" if llm_config is not None else None

    if llm_config is None:
        try:
            env_config = load_config_from_env()
        except LLMConfigurationError:
            env_config = None
        llm_config = env_config
        llm_source = "environment" if env_config is not None else None

    return ConfigStatusResponse(
        embedding_configured=embedding_config is not None,
        embedding_provider=embedding_config.provider if embedding_config else None,
        embedding_model=embedding_config.model if embedding_config else None,
        llm_configured=llm_config is not None,
        llm_provider=llm_config.provider if llm_config else None,
        llm_model=llm_config.model if llm_config else None,
        llm_source=llm_source,
    )


@app.get("/stats", response_model=VectorStatsResponse)
def stats() -> VectorStatsResponse:
    try:
        embedding = get_embeddings_or_raise()
        vector_stats = get_vector_store_stats(embedding)
    except ConfigurationError as exc:
        return VectorStatsResponse(
            embedding_configured=False,
            error=str(exc),
        )
    except Exception as exc:
        return VectorStatsResponse(
            embedding_configured=True,
            error=f"读取向量库状态失败: {exc}",
        )

    return VectorStatsResponse(
        embedding_configured=True,
        total_chunks=vector_stats.total_chunks,
        files=vector_stats.files,
    )


@app.post("/index", response_model=IndexResponse)
def index(request: IndexRequest) -> IndexResponse:
    try:
        result = index_documents(
            request.directory,
            splitter=request.splitter,
            recursive=request.recursive,
            reindex=request.reindex,
            prune_deleted=request.prune_deleted,
        )
    except ConfigurationError as exc:
        raise _safe_http_error(400, str(exc)) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise _safe_http_error(400, str(exc)) from exc
    except Exception as exc:
        raise _safe_http_error(500, f"入库失败: {exc}") from exc

    return IndexResponse(
        documents=len(result.documents),
        chunks=len(result.chunks),
        added=result.added,
        skipped=result.skipped,
        total_chunks=result.total_chunks,
        file_count=result.file_count,
    )


@app.post("/retrieve", response_model=RetrievalResponse)
def semantic_retrieve(request: RetrievalRequest) -> RetrievalResponse:
    try:
        result = retrieve(
            request.query,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            include_scores=True,
        )
    except ConfigurationError as exc:
        raise _safe_http_error(400, str(exc)) from exc
    except Exception as exc:
        raise _safe_http_error(500, f"检索失败: {exc}") from exc

    chunks = [
        RetrievedChunk(
            index=index,
            score=score,
            content=doc.page_content,
            metadata=_metadata_to_dict(doc.metadata),
        )
        for index, (doc, score) in enumerate(result.scored_results, 1)
    ]
    return RetrievalResponse(
        query=result.query,
        total_chunks=result.stats.total_chunks,
        results=chunks,
    )


@app.post("/answer", response_model=AnswerResponse)
def answer(request: AnswerRequest) -> AnswerResponse:
    try:
        result = answer_question(
            request.query,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            context_max_chars=request.context_max_chars,
        )
    except (ConfigurationError, LLMConfigurationError, ValueError) as exc:
        raise _safe_http_error(400, str(exc)) from exc
    except Exception as exc:
        raise _safe_http_error(500, f"问答失败: {exc}") from exc

    return AnswerResponse(
        question=result.question,
        answer=result.answer,
        sources=[
            SourceReferenceResponse(
                index=source.index,
                filename=source.filename,
                source_id=source.source_id,
                chunk_id=source.chunk_id,
                score=source.score,
                excerpt=source.excerpt,
            )
            for source in result.sources
        ],
        total_chunks=result.retrieval.stats.total_chunks,
    )
