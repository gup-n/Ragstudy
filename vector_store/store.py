"""向量存储核心操作——基于 ChromaDB。

职责：
  1. 将文档 Chunks 存入 ChromaDB（自动向量化）
  2. 相似检索（query → embed → top-k）
  3. 提供 Retriever 供后续 Chain 组装
"""

import logging
from typing import List, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStoreRetriever

from vector_store.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_PERSIST_DIR,
    DEFAULT_TOP_K,
)

logger = logging.getLogger(__name__)


def _get_store(embedding: Embeddings) -> Chroma:
    """获取 ChromaDB 实例（自动创建/加载持久化目录）。"""
    CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=CHROMA_COLLECTION_NAME,
        embedding_function=embedding,
        persist_directory=str(CHROMA_PERSIST_DIR),
    )


def add_to_store(
    chunks: List[Document],
    embedding: Embeddings,
) -> int:
    """将文档 Chunks 向量化后存入 ChromaDB。

    Args:
        chunks: 切割后的文档片段列表。
        embedding: Embedding 模型实例（用于将文本转为向量）。

    Returns:
        入库的文档数量。
    """
    store = _get_store(embedding)
    ids = store.add_documents(chunks)
    logger.info(
        "向量入库完成: %d 个 Chunks → %s",
        len(ids),
        CHROMA_PERSIST_DIR,
    )
    return len(ids)


def search(
    query: str,
    embedding: Embeddings,
    k: int = DEFAULT_TOP_K,
    score_threshold: Optional[float] = None,
) -> List[Document]:
    """语义检索：查询 → Embed → 相似度排序 → 返回 top-k。

    Args:
        query: 用户查询文本。
        embedding: Embedding 模型实例。
        k: 返回的最相似文档数量。
        score_threshold: 可选的最低相似度阈值。

    Returns:
        按相似度降序排列的 Document 列表。
    """
    store = _get_store(embedding)

    if score_threshold is not None:
        retriever = store.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={"k": k, "score_threshold": score_threshold},
        )
    else:
        retriever = store.as_retriever(
            search_kwargs={"k": k},
        )

    results = retriever.invoke(query)

    logger.info(
        "检索完成: query='%s' → %d 个结果",
        query[:50] + ("..." if len(query) > 50 else ""),
        len(results),
    )
    return results


def get_retriever(
    embedding: Embeddings,
    k: int = DEFAULT_TOP_K,
) -> VectorStoreRetriever:
    """获取 Retriever 实例，供后续 Chain 组装。

    Args:
        embedding: Embedding 模型实例。
        k: 默认检索数量。

    Returns:
        LangChain VectorStoreRetriever 实例。
    """
    store = _get_store(embedding)
    return store.as_retriever(search_kwargs={"k": k})


def count_documents(embedding: Embeddings) -> int:
    """查询向量库中的文档总数。"""
    store = _get_store(embedding)
    return store._collection.count()


def delete_all(embedding: Embeddings) -> None:
    """清空向量库中的所有文档。"""
    store = _get_store(embedding)
    ids = store._collection.get()["ids"]
    if ids:
        store.delete(ids)
        logger.info("已清空向量库: 移除 %d 个文档", len(ids))
