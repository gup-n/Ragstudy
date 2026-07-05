"""RAG 管线服务层。

CLI、演示脚本和未来 Web API 都应优先复用这里的函数，避免把业务逻辑散落在
不同入口脚本中。
"""

from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from data_loader import load_documents
from data_splitter import split_documents
from embedding import get_embedding, init_db
from vector_store import (
    add_to_store,
    count_documents,
    force_reindex,
    get_file_list,
    search,
    search_with_scores,
)


class ConfigurationError(RuntimeError):
    """缺少或无法创建运行所需配置。"""


@dataclass(frozen=True)
class PipelineResult:
    documents: list[Document]
    chunks: list[Document]


@dataclass(frozen=True)
class EmbeddingValidationResult:
    embedding_name: str
    vector_dimensions: list[int]


@dataclass(frozen=True)
class IndexResult:
    documents: list[Document]
    chunks: list[Document]
    added: int
    skipped: int
    total_chunks: int
    file_count: int


@dataclass(frozen=True)
class VectorStoreStats:
    total_chunks: int
    files: list[str]


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    results: list[Document]
    scored_results: list[tuple[Document, float]]
    stats: VectorStoreStats


def get_embeddings_or_raise() -> Embeddings:
    """初始化数据库并获取当前启用的 Embedding 模型。"""
    init_db()
    embedding = get_embedding()
    if embedding is None:
        raise ConfigurationError("未配置 Embedding Provider")
    return embedding


def load_and_split(
    directory: str | None = None,
    *,
    splitter: str = "recursive",
    recursive: bool = True,
    strict_load: bool = False,
) -> PipelineResult:
    """加载并切割文档。"""
    documents = load_documents(directory, recursive=recursive, strict=strict_load)
    chunks = split_documents(documents, splitter)
    return PipelineResult(documents=documents, chunks=chunks)


def validate_embedding(
    chunks: list[Document],
    embedding: Embeddings,
    *,
    sample_size: int = 3,
) -> EmbeddingValidationResult:
    """用少量 Chunk 验证 Embedding 是否可用。"""
    sample_texts = [chunk.page_content[:200] for chunk in chunks[:sample_size]]
    if not sample_texts:
        return EmbeddingValidationResult(
            embedding_name=embedding.__class__.__name__,
            vector_dimensions=[],
        )
    vectors = embedding.embed_documents(sample_texts)
    return EmbeddingValidationResult(
        embedding_name=embedding.__class__.__name__,
        vector_dimensions=[len(vector) for vector in vectors],
    )


def index_documents(
    directory: str | None = None,
    *,
    splitter: str = "recursive",
    recursive: bool = True,
    reindex: bool = False,
    prune_deleted: bool = False,
) -> IndexResult:
    """加载、切割并写入向量库。"""
    pipeline = load_and_split(
        directory,
        splitter=splitter,
        recursive=recursive,
        # 清理已删除文件依赖“本次扫描完整可信”。若存在解析失败，不能把缺失结果当作删除。
        strict_load=prune_deleted,
    )
    embedding = get_embeddings_or_raise()

    # 全量重建和增量入库共用同一套加载结果，保证 CLI 与未来 API 行为一致。
    if reindex:
        added = force_reindex(pipeline.chunks, embedding)
        skipped = 0
    else:
        added, skipped = add_to_store(
            pipeline.chunks,
            embedding,
            prune_deleted=prune_deleted,
        )

    return IndexResult(
        documents=pipeline.documents,
        chunks=pipeline.chunks,
        added=added,
        skipped=skipped,
        total_chunks=count_documents(embedding),
        file_count=len(get_file_list(embedding)),
    )


def get_vector_store_stats(embedding: Embeddings | None = None) -> VectorStoreStats:
    """读取向量库统计信息。"""
    embedding = embedding or get_embeddings_or_raise()
    files = get_file_list(embedding)
    return VectorStoreStats(
        total_chunks=count_documents(embedding),
        files=files,
    )


def retrieve(
    query: str,
    *,
    top_k: int = 5,
    score_threshold: float | None = None,
    include_scores: bool = True,
    embedding: Embeddings | None = None,
) -> RetrievalResult:
    """执行语义检索。"""
    embedding = embedding or get_embeddings_or_raise()
    stats = get_vector_store_stats(embedding)
    if stats.total_chunks == 0:
        # 空库直接短路，避免对 Chroma 发起没有意义的相似度查询。
        return RetrievalResult(
            query=query,
            results=[],
            scored_results=[],
            stats=stats,
        )

    if include_scores:
        scored = search_with_scores(
            query,
            embedding,
            k=top_k,
            score_threshold=score_threshold,
        )
        results = [doc for doc, _score in scored]
    else:
        results = search(
            query,
            embedding,
            k=top_k,
            score_threshold=score_threshold,
        )
        scored = []

    return RetrievalResult(
        query=query,
        results=results,
        scored_results=scored,
        stats=stats,
    )
