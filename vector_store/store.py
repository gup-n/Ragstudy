"""向量存储核心操作——基于 ChromaDB。

职责：
  1. 将文档 Chunks 存入 ChromaDB（增量模式：跳过未变、替换已变）
  2. 语义检索（query → embed → top-k）
  3. 提供 Retriever 供后续 Chain 组装

增量入库策略：
  - 每篇文档入库时，在 ChromaDB metadata 中记录 source_id + 文件指纹
  - 下次入库前对比：
    · 新文件 → 直接入库
    · 已变更文件（内容哈希或 mtime/size 不同）→ 先删旧向量，再重新入库
    · 未变更文件 → 跳过
"""

import hashlib
import logging
import os
from collections import defaultdict
from pathlib import Path
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

# metadata 中记录文件身份与指纹的字段名
_META_SOURCE_ID = "source_id"
_META_DOC_ROOT = "doc_root"
_META_MTIME = "file_mtime"
_META_SIZE = "file_size"
_META_CONTENT_HASH = "content_hash"
_META_CHUNK_ID = "chunk_id"


def _get_store(embedding: Embeddings) -> Chroma:
    """获取 ChromaDB 实例（自动创建/加载持久化目录）。"""
    CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=CHROMA_COLLECTION_NAME,
        embedding_function=embedding,
        persist_directory=str(CHROMA_PERSIST_DIR),
    )


def _hash_file(filepath: Path) -> str:
    """计算文件内容哈希，用于比 mtime/size 更可靠的增量判断。"""
    digest = hashlib.sha256()
    with filepath.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _get_file_fingerprint(filepath: str) -> dict[str, float | int | str]:
    """获取文件的 mtime、size 和内容哈希。"""
    path = Path(filepath)
    stat = path.stat()
    return {
        _META_MTIME: stat.st_mtime,
        _META_SIZE: stat.st_size,
        _META_CONTENT_HASH: _hash_file(path),
    }


def _get_source_id(chunk: Document) -> str:
    """获取 Chunk 对应的稳定源文件 ID。"""
    source_id = chunk.metadata.get(_META_SOURCE_ID)
    if source_id:
        return str(source_id)

    # 兼容旧数据和手工构造的 Document，优先使用相对路径避免同名文件冲突。
    relative_path = chunk.metadata.get("relative_path")
    if relative_path:
        return str(relative_path)

    source = chunk.metadata.get("source")
    if source:
        return os.path.normpath(str(source))

    return str(chunk.metadata.get("filename", "unknown"))


def _enrich_metadata(chunks: List[Document]) -> None:
    """为每个 Chunk 补全文件指纹 metadata（直接修改原对象）。

    从 metadata["source"] 读取文件路径，查询文件系统获取 mtime、size 和内容哈希。
    """
    for chunk in chunks:
        chunk.metadata[_META_SOURCE_ID] = _get_source_id(chunk)
        source = chunk.metadata.get("source")
        if source and os.path.isfile(source):
            chunk.metadata.update(_get_file_fingerprint(source))


def _ensure_chunk_ids(chunks: List[Document]) -> list[str]:
    """确保每个 Chunk 都有稳定 ID，并返回与 chunks 对齐的 ID 列表。"""
    counters: dict[str, int] = defaultdict(int)
    ids: list[str] = []

    for chunk in chunks:
        source_id = _get_source_id(chunk)
        if "chunk_index" not in chunk.metadata:
            chunk.metadata["chunk_index"] = counters[source_id]
        counters[source_id] = max(
            counters[source_id],
            int(chunk.metadata["chunk_index"]) + 1,
        )

        chunk_id = chunk.metadata.get(_META_CHUNK_ID)
        if not chunk_id:
            chunk_id = f"{source_id}::chunk-{chunk.metadata['chunk_index']}"
            chunk.metadata[_META_CHUNK_ID] = chunk_id
        ids.append(str(chunk_id))

    return ids


def _group_by_source_id(chunks: List[Document]) -> Dict[str, List[Document]]:
    """按 source_id 对 Chunks 分组。"""
    groups: Dict[str, List[Document]] = defaultdict(list)
    for chunk in chunks:
        groups[_get_source_id(chunk)].append(chunk)
    return dict(groups)


def _fingerprint_matches(stored: dict, current: dict) -> bool:
    """比较已入库指纹与当前文件指纹，优先使用内容哈希。"""
    stored_hash = stored.get(_META_CONTENT_HASH)
    current_hash = current.get(_META_CONTENT_HASH)
    if stored_hash and current_hash:
        return stored_hash == current_hash

    # 兼容历史索引：旧向量没有 content_hash 时退回 mtime 与 size。
    return (
        stored.get("mtime") == current.get(_META_MTIME)
        and stored.get("size") == current.get(_META_SIZE)
    )


# ---------------------------------------------------------------------------
# 文件索引：从向量库对比文件指纹
# ---------------------------------------------------------------------------


def get_stored_file_index(embedding: Embeddings) -> Dict[str, Dict]:
    """查询向量库中所有文件的指纹索引。

    Returns:
        {source_id: {"mtime": float, "size": int, "content_hash": str}, ...}
        始终返回完整索引（不含 id 列表以避免大结果集内存溢出），
        若向量库为空则返回空字典。
    """
    store = _get_store(embedding)
    # 仅获取 metadata，不加 ids 和 documents 以减少数据传输
    metadata_list = store.get(include=["metadatas"])["metadatas"]

    if not metadata_list:
        return {}

    index: Dict[str, Dict] = {}
    for meta in metadata_list:
        if not meta:
            continue
        source_id = (
            meta.get(_META_SOURCE_ID)
            or meta.get("relative_path")
            or meta.get("filename")
        )
        if source_id and source_id not in index:
            index[source_id] = {
                "mtime": meta.get(_META_MTIME),
                "size": meta.get(_META_SIZE),
                _META_CONTENT_HASH: meta.get(_META_CONTENT_HASH),
                "filename": meta.get("filename"),
                "source": meta.get("source"),
                _META_DOC_ROOT: meta.get(_META_DOC_ROOT),
            }
    return index


# ---------------------------------------------------------------------------
# 删除
# ---------------------------------------------------------------------------


def delete_by_source_ids(embedding: Embeddings, source_ids: List[str]) -> int:
    """删除指定 source_id 的所有向量。

    Args:
        embedding: Embedding 模型实例。
        source_ids: 要删除的源文件 ID 列表。

    Returns:
        删除的向量数量。
    """
    store = _get_store(embedding)

    total = 0
    for source_id in source_ids:
        results = store.get(
            where={_META_SOURCE_ID: source_id},
            include=["metadatas"],
        )
        ids = results["ids"]

        # 兼容历史数据：旧版本只记录 filename。
        if not ids:
            legacy = store.get(where={"filename": source_id}, include=["metadatas"])
            ids = legacy["ids"]

        if ids:
            store.delete(ids)
            total += len(ids)
            logger.info("  删除旧数据: %s → %d 个 Chunks", source_id, len(ids))

    return total


def delete_by_filenames(embedding: Embeddings, filenames: List[str]) -> int:
    """删除指定文件名的所有向量，保留给旧调用方兼容使用。"""
    store = _get_store(embedding)

    total = 0
    for fname in filenames:
        results = store.get(where={"filename": fname}, include=["metadatas"])
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
    *,
    prune_deleted: bool = False,
) -> Tuple[int, int]:
    """增量入库：跳过未变文件，替换已变文件，新增新文件。

    Args:
        chunks: 切割后的文档片段列表。
        embedding: Embedding 模型实例。
        prune_deleted: 是否清理本次扫描目录中已删除的历史文件向量。

    Returns:
        (本次新增/更新的 Chunks 数量, 跳过的 Chunks 数量)。
    """
    if not chunks:
        return 0, 0

    # 补全文件指纹
    _enrich_metadata(chunks)

    # 按文件分组
    file_groups = _group_by_source_id(chunks)
    current_source_ids = set(file_groups)
    current_doc_roots = {
        str(group[0].metadata.get(_META_DOC_ROOT))
        for group in file_groups.values()
        if group[0].metadata.get(_META_DOC_ROOT)
    }

    # 查询已有索引
    stored_index = get_stored_file_index(embedding)
    logger.info("向量库中已有 %d 个文件的记录", len(stored_index))

    # 对比分类
    to_add: List[Document] = []
    to_delete: List[str] = []
    skipped = 0

    for source_id, doc_group in file_groups.items():
        # 取该组第一条 metadata 中的指纹（同一文件所有 chunk 相同）
        sample = doc_group[0].metadata

        stored = stored_index.get(source_id)
        display_name = (
            sample.get("relative_path")
            or sample.get("filename")
            or source_id
        )

        if stored is None:
            # ✅ 新文件——直接入库
            to_add.extend(doc_group)
            logger.info("  新文件: %s (%d Chunks)", display_name, len(doc_group))
        elif _fingerprint_matches(stored, sample):
            # ✅ 未变更——跳过
            skipped += len(doc_group)
            logger.info("  跳过(未变): %s (%d Chunks)", display_name, len(doc_group))
        else:
            # ✅ 已变更——先删旧，再入库
            to_delete.append(source_id)
            to_add.extend(doc_group)
            logger.info(
                "  已变更: %s (%d Chunks, 文件指纹已变)",
                display_name,
                len(doc_group),
            )

    if prune_deleted and current_doc_roots:
        # 只清理本次扫描根目录内的历史数据，避免误删其他知识库目录。
        stale_source_ids = [
            source_id
            for source_id, meta in stored_index.items()
            if source_id not in current_source_ids
            and meta.get(_META_DOC_ROOT) in current_doc_roots
        ]
        if stale_source_ids:
            to_delete.extend(stale_source_ids)
            logger.info("  待清理已删除文件: %d 个", len(stale_source_ids))

    # 执行删除
    deleted_count = 0
    if to_delete:
        deleted_count = delete_by_source_ids(embedding, sorted(set(to_delete)))

    # 执行入库
    added_count = 0
    if to_add:
        store = _get_store(embedding)
        ids = store.add_documents(to_add, ids=_ensure_chunk_ids(to_add))
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
    ids = store.add_documents(chunks, ids=_ensure_chunk_ids(chunks))
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
    if score_threshold is not None:
        return [
            doc
            for doc, _score in search_with_scores(
                query,
                embedding,
                k=k,
                score_threshold=score_threshold,
            )
        ]

    store = _get_store(embedding)

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


def search_with_scores(
    query: str,
    embedding: Embeddings,
    k: int = DEFAULT_TOP_K,
    score_threshold: Optional[float] = None,
) -> List[Tuple[Document, float]]:
    """语义检索并返回归一化相关性分数。"""
    store = _get_store(embedding)
    kwargs = {"k": k}
    if score_threshold is not None:
        kwargs["score_threshold"] = score_threshold

    results = store.similarity_search_with_relevance_scores(query, **kwargs)

    logger.info(
        "检索完成: query='%s' → %d 个带分数结果",
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
    collection = getattr(store, "_collection", None)
    if collection is not None and hasattr(collection, "count"):
        return collection.count()
    return len(store.get(include=["metadatas"]).get("ids", []))


def get_file_list(embedding: Embeddings) -> List[str]:
    """查询向量库中所有文件名列表。"""
    index = get_stored_file_index(embedding)
    return sorted(index.keys())


def delete_all(embedding: Embeddings) -> None:
    """清空向量库中的所有文档。"""
    store = _get_store(embedding)
    ids = store.get(include=["metadatas"]).get("ids", [])
    if ids:
        store.delete(ids)
        logger.info("已清空向量库: 移除 %d 个文档", len(ids))
