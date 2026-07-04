"""向量存储核心操作——基于 ChromaDB。

职责：
  1. 将文档 Chunks 存入 ChromaDB（增量模式：跳过未变、替换已变）
  2. 语义检索（query → embed → top-k）
  3. 提供 Retriever 供后续 Chain 组装

增量入库策略：
  - 每篇文档入库时，在 ChromaDB metadata 中记录 file_mtime + file_size
  - 下次入库前对比：
    · 新文件 → 直接入库
    · 已变更文件（mtime/size 不同）→ 先删旧向量，再重新入库
    · 未变更文件 → 跳过
"""

import logging
import os
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

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

# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

# metadata 中记录文件指纹的字段名
_META_MTIME = "file_mtime"
_META_SIZE = "file_size"


def _get_store(embedding: Embeddings) -> Chroma:
    """获取 ChromaDB 实例（自动创建/加载持久化目录）。"""
    CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=CHROMA_COLLECTION_NAME,
        embedding_function=embedding,
        persist_directory=str(CHROMA_PERSIST_DIR),
    )


def _get_file_fingerprint(filepath: str) -> Tuple[float, int]:
    """获取文件的 mtime（修改时间）和 size（字节数）。"""
    stat = os.stat(filepath)
    return stat.st_mtime, stat.st_size


def _enrich_metadata(chunks: List[Document]) -> None:
    """为每个 Chunk 补全文件指纹 metadata（直接修改原对象）。

    从 metadata["source"] 读取文件路径，查询文件系统获取 mtime 和 size。
    """
    for chunk in chunks:
        source = chunk.metadata.get("source")
        if source and os.path.isfile(source):
            mtime, size = _get_file_fingerprint(source)
            chunk.metadata[_META_MTIME] = mtime
            chunk.metadata[_META_SIZE] = size


def _group_by_filename(chunks: List[Document]) -> Dict[str, List[Document]]:
    """按 filename 对 Chunks 分组。"""
    groups: Dict[str, List[Document]] = defaultdict(list)
    for chunk in chunks:
        fname = chunk.metadata.get("filename", "unknown")
        groups[fname].append(chunk)
    return dict(groups)


# ---------------------------------------------------------------------------
# 文件索引：从向量库对比文件指纹
# ---------------------------------------------------------------------------


def get_stored_file_index(embedding: Embeddings) -> Dict[str, Dict]:
    """查询向量库中所有文件的指纹索引。

    Returns:
        {filename: {"mtime": float, "size": int}, ...}
        始终返回完整索引（不含 id 列表以避免大结果集内存溢出），
        若向量库为空则返回空字典。
    """
    store = _get_store(embedding)
    # 仅获取 metadata，不加 ids 和 documents 以减少数据传输
    metadata_list = store._collection.get(include=["metadatas"])["metadatas"]

    if not metadata_list:
        return {}

    index: Dict[str, Dict] = {}
    for meta in metadata_list:
        if not meta:
            continue
        fname = meta.get("filename")
        if fname and fname not in index:
            index[fname] = {
                "mtime": meta.get(_META_MTIME),
                "size": meta.get(_META_SIZE),
            }
    return index


# ---------------------------------------------------------------------------
# 删除
# ---------------------------------------------------------------------------


def delete_by_filenames(embedding: Embeddings, filenames: List[str]) -> int:
    """删除指定文件的所有向量。

    Args:
        embedding: Embedding 模型实例。
        filenames: 要删除的文件名列表。

    Returns:
        删除的向量数量。
    """
    store = _get_store(embedding)

    total = 0
    for fname in filenames:
        results = store._collection.get(
            where={"filename": fname},
            include=[],
        )
        ids = results["ids"]
        if ids:
            store.delete(ids)
            total += len(ids)
            logger.info("  删除旧数据: %s → %d 个 Chunks", fname, len(ids))

    return total


# ---------------------------------------------------------------------------
# 入库
# ---------------------------------------------------------------------------


def add_to_store(
    chunks: List[Document],
    embedding: Embeddings,
) -> Tuple[int, int]:
    """增量入库：跳过未变文件，替换已变文件，新增新文件。

    Args:
        chunks: 切割后的文档片段列表。
        embedding: Embedding 模型实例。

    Returns:
        (本次新增/更新的 Chunks 数量, 跳过的 Chunks 数量)。
    """
    if not chunks:
        return 0, 0

    # 补全文件指纹
    _enrich_metadata(chunks)

    # 按文件分组
    file_groups = _group_by_filename(chunks)

    # 查询已有索引
    stored_index = get_stored_file_index(embedding)
    logger.info("向量库中已有 %d 个文件的记录", len(stored_index))

    # 对比分类
    to_add: List[Document] = []
    to_delete: List[str] = []
    skipped = 0

    for fname, doc_group in file_groups.items():
        # 取该组第一条 metadata 中的指纹（同一文件所有 chunk 相同）
        sample = doc_group[0].metadata
        current_mtime = sample.get(_META_MTIME)
        current_size = sample.get(_META_SIZE)

        stored = stored_index.get(fname)

        if stored is None:
            # ✅ 新文件——直接入库
            to_add.extend(doc_group)
            logger.info("  新文件: %s (%d Chunks)", fname, len(doc_group))
        elif (
            stored.get("mtime") == current_mtime
            and stored.get("size") == current_size
        ):
            # ✅ 未变更——跳过
            skipped += len(doc_group)
            logger.info("  跳过(未变): %s (%d Chunks)", fname, len(doc_group))
        else:
            # ✅ 已变更——先删旧，再入库
            to_delete.append(fname)
            to_add.extend(doc_group)
            logger.info(
                "  已变更: %s (%d Chunks, mtime/size 已变)",
                fname,
                len(doc_group),
            )

    # 执行删除
    deleted_count = 0
    if to_delete:
        deleted_count = delete_by_filenames(embedding, to_delete)

    # 执行入库
    added_count = 0
    if to_add:
        store = _get_store(embedding)
        ids = store.add_documents(to_add)
        added_count = len(ids)
        logger.info("  新增入库: %d 个 Chunks", added_count)

    # 汇总
    logger.info(
        "入库汇总: +%d / -%d / =%d (跳过)",
        added_count,
        deleted_count,
        skipped,
    )

    # 最终存量
    total = count_documents(embedding)
    logger.info("向量库总 Chunks: %d", total)

    return added_count, skipped


def force_reindex(
    chunks: List[Document],
    embedding: Embeddings,
) -> int:
    """强制全量重建索引（清空后重新入库）。

    Args:
        chunks: 切割后的文档片段列表。
        embedding: Embedding 模型实例。

    Returns:
        入库的 Chunks 数量。
    """
    delete_all(embedding)
    _enrich_metadata(chunks)
    store = _get_store(embedding)
    ids = store.add_documents(chunks)
    logger.info("全量重建完成: %d 个 Chunks", len(ids))
    return len(ids)


# ---------------------------------------------------------------------------
# 检索
# ---------------------------------------------------------------------------


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
    """获取 Retriever 实例，供后续 Chain 组装。"""
    store = _get_store(embedding)
    return store.as_retriever(search_kwargs={"k": k})


def count_documents(embedding: Embeddings) -> int:
    """查询向量库中的文档总数。"""
    store = _get_store(embedding)
    return store._collection.count()


def get_file_list(embedding: Embeddings) -> List[str]:
    """查询向量库中所有文件名列表。"""
    index = get_stored_file_index(embedding)
    return sorted(index.keys())


def delete_all(embedding: Embeddings) -> None:
    """清空向量库中的所有文档。"""
    store = _get_store(embedding)
    ids = store._collection.get()["ids"]
    if ids:
        store.delete(ids)
        logger.info("已清空向量库: 移除 %d 个文档", len(ids))
