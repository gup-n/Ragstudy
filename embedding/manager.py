"""Manager —— Embedding 模块的统一对外接口。

上层模块（含 GUI）只通过此模块获取 Embedding 实例。
不直接调用 Factory 或 CRUD。
"""

import logging

from langchain_core.embeddings import Embeddings

from embedding.factory import create_embeddings

logger = logging.getLogger(__name__)


def get_embedding() -> Embeddings | None:
    """获取当前启用的 Embedding 模型。

    内部流程：
        1. 读取数据库中的 enabled 配置
        2. 无配置 → 返回 None（由 GUI 决定下一步）
        3. 有配置 → Factory 创建 Embeddings 实例
        4. 返回 Embeddings 实例

    Returns:
        Embeddings 实例，或 None（无可用配置时）。
    """
    from embedding.crud import get_enabled_config

    config = get_enabled_config()

    if config is None:
        logger.info("No embedding config found in database.")
        return None

    logger.info(
        "Loaded embedding config: provider=%s model=%s",
        config.provider,
        config.model,
    )
    return create_embeddings(config)
