"""向量存储配置。"""

from pathlib import Path

# ChromaDB 持久化目录
CHROMA_PERSIST_DIR = Path(__file__).resolve().parent.parent / "Data/vector_store"

# 默认 Collection 名称
CHROMA_COLLECTION_NAME = "rag_docs"

# 默认检索数量
DEFAULT_TOP_K = 5
