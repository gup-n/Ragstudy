"""Vector Store 模块 —— 向量存储与语义检索。

基于 ChromaDB 实现，支持持久化。

公开 API：
    add_to_store(chunks, embedding)    文档 Chunks 入库
    search(query, embedding, k=5)      语义检索
    get_retriever(embedding, k=5)      获取 Retriever
    count_documents(embedding)         查询文档总数
    delete_all(embedding)              清空向量库

使用示例：
    from data_loader import load_documents
    from data_splitter import split_documents
    from embedding import get_embedding, init_db
    from vector_store import add_to_store, search

    init_db()
    emb = get_embedding()
    if emb is None:
        print("请先配置 Embedding Provider")

    docs = load_documents()
    chunks = split_documents(docs)
    add_to_store(chunks, emb)

    results = search("你的问题", emb)
    for r in results:
        print(r.page_content[:200])
"""

from vector_store.store import (
    add_to_store,
    count_documents,
    delete_all,
    get_retriever,
    search,
)

__all__ = [
    "add_to_store",
    "search",
    "get_retriever",
    "count_documents",
    "delete_all",
]
