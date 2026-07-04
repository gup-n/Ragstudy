"""Embedding 模块 —— RAG 管线的向量化引擎。

公开 API：
    get_embedding()         获取当前启用的 Embedding 模型（统一入口）
    init_db()               初始化数据库（应用启动时调用一次）
    get_enabled_config()    获取数据库中的 Embedding 配置
    save_config()           保存 Embedding 配置
    delete_config()         删除 Embedding 配置
    download_huggingface_model()  下载 HuggingFace 模型

使用示例：
    from embedding import get_embedding

    emb = get_embedding()
    if emb is None:
        # GUI 显示初始化向导
        ...
    else:
        vectors = emb.embed_documents(["text1", "text2"])
"""

from embedding.crud import delete_config, get_enabled_config, save_config
from embedding.database import init_db
from embedding.downloader import download_huggingface_model
from embedding.manager import get_embedding
from embedding.schema import (
    EmbeddingConfig,
    EmbeddingError,
    ProviderNotFoundError,
)

__all__ = [
    "get_embedding",
    "init_db",
    "get_enabled_config",
    "save_config",
    "delete_config",
    "download_huggingface_model",
    "EmbeddingConfig",
    "EmbeddingError",
    "ProviderNotFoundError",
]
