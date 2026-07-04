"""Embedding 工厂 —— 根据配置创建 Embeddings 实例。"""

import logging

from langchain_core.embeddings import Embeddings

from embedding.providers import PROVIDERS
from embedding.schema import EmbeddingConfig, ProviderNotFoundError

logger = logging.getLogger(__name__)


def create_embeddings(config: EmbeddingConfig) -> Embeddings:
    """根据 EmbeddingConfig 创建 Embeddings 实例。

    Args:
        config: Embedding 配置（api_key 应已解密）。

    Returns:
        LangChain Embeddings 实例。

    Raises:
        ProviderNotFoundError: config.provider 未在 PROVIDERS 中注册。
    """
    factory = PROVIDERS.get(config.provider)
    if factory is None:
        raise ProviderNotFoundError(config.provider)

    logger.info("Creating embeddings: provider=%s model=%s", config.provider, config.model)
    return factory(config)
