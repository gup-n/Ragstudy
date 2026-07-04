"""Vector Store 模块 —— 向量存储与语义检索。

基于 ChromaDB 实现，支持增量入库和持久化。

公开 API：
    add_to_store(chunks, embedding)      增量入库（跳过未变、替换已变）
    force_reindex(chunks, embedding)     强制全量重建
    search(query, embedding, k=5)        语义检索
    get_retriever(embedding, k=5)        获取 Retriever
    count_documents(embedding)           查询文档总数
    get_file_list(embedding)             查询已入库的文件列表
    get_stored_file_index(embedding)     查询文件指纹索引
    delete_by_filenames(embedding, [])   按文件名删除向量
    delete_all(embedding)                清空向量库
"""

from vector_store.store import (
    add_to_store,
    count_documents,
    delete_all,
    delete_by_filenames,
    force_reindex,
    get_file_list,
    get_retriever,
    get_stored_file_index,
    search,
)

__all__ = [
    "add_to_store",
    "force_reindex",
    "search",
    "get_retriever",
    "count_documents",
    "get_file_list",
    "get_stored_file_index",
    "delete_by_filenames",
    "delete_all",
]
