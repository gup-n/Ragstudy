from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str
    service: str


class ConfigStatusResponse(BaseModel):
    embedding_configured: bool
    embedding_provider: str | None = None
    embedding_model: str | None = None
    llm_configured: bool
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_source: Literal["database", "environment", None] = None


class VectorStatsResponse(BaseModel):
    embedding_configured: bool
    total_chunks: int = 0
    files: list[str] = Field(default_factory=list)
    error: str | None = None


class IndexRequest(BaseModel):
    directory: str | None = None
    splitter: Literal["recursive", "character"] = "recursive"
    recursive: bool = True
    reindex: bool = False
    prune_deleted: bool = False


class IndexResponse(BaseModel):
    documents: int
    chunks: int
    added: int
    skipped: int
    total_chunks: int
    file_count: int


class RetrievalRequest(BaseModel):
    query: str
    top_k: int = 5
    score_threshold: float | None = None

    @field_validator("query")
    @classmethod
    def clean_query(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("query 不能为空")
        return stripped

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("top_k 必须大于 0")
        return v

    @field_validator("score_threshold")
    @classmethod
    def validate_score_threshold(cls, v: float | None) -> float | None:
        if v is not None and not 0 <= v <= 1:
            raise ValueError("score_threshold 必须在 0 到 1 之间")
        return v


class RetrievedChunk(BaseModel):
    index: int
    score: float | None
    content: str
    metadata: dict[str, Any]


class RetrievalResponse(BaseModel):
    query: str
    total_chunks: int
    results: list[RetrievedChunk]


class AnswerRequest(RetrievalRequest):
    context_max_chars: int = 12000

    @field_validator("context_max_chars")
    @classmethod
    def validate_context_max_chars(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("context_max_chars 必须大于 0")
        return v


class SourceReferenceResponse(BaseModel):
    index: int
    filename: str
    source_id: str
    chunk_id: str
    score: float | None
    excerpt: str


class AnswerResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceReferenceResponse]
    total_chunks: int
