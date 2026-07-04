"""Provider 注册表与工厂函数。

每个 Provider 对应一个工厂函数，接受 EmbeddingConfig 返回 Embeddings 实例。

新增 Provider 只需在此文件添加函数并在 PROVIDERS 字典注册即可，
Factory / Manager / GUI 均无需修改。
"""

import logging
from typing import Any

from langchain_core.embeddings import Embeddings

from embedding.config import (
    HF_MODEL_CACHE_DIR,
    OLLAMA_DEFAULT_BASE_URL,
)
from embedding.schema import EmbeddingConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider 工厂函数
# ---------------------------------------------------------------------------


def _create_huggingface(config: EmbeddingConfig) -> Embeddings:
    """创建 HuggingFace Embeddings 实例。"""
    from langchain_huggingface import HuggingFaceEmbeddings

    extra = config.extra or {}

    model_kwargs = dict(extra.get("model_kwargs") or {})
    if "device" in extra:
        model_kwargs.setdefault("device", extra["device"])

    encode_kwargs = dict(extra.get("encode_kwargs") or {})
    encode_kwargs.setdefault("normalize_embeddings", True)

    return HuggingFaceEmbeddings(
        model_name=config.model,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs,
        cache_folder=str(HF_MODEL_CACHE_DIR),
    )


def _create_ollama(config: EmbeddingConfig) -> Embeddings:
    """创建 Ollama Embeddings 实例。"""
    from langchain_ollama import OllamaEmbeddings

    kwargs: dict[str, Any] = dict(config.extra or {})
    kwargs["model"] = config.model
    kwargs["base_url"] = config.base_url or OLLAMA_DEFAULT_BASE_URL

    return OllamaEmbeddings(**kwargs)


def _create_openai_compatible(config: EmbeddingConfig) -> Embeddings:
    """创建 OpenAI Compatible Embeddings 实例。

    兼容 OpenAI、DeepSeek、硅基流动、OpenRouter、OneAPI 等
    所有兼容 OpenAI API 的服务商。
    """
    from langchain_openai import OpenAIEmbeddings

    kwargs: dict[str, Any] = dict(config.extra or {})
    kwargs["model"] = config.model
    kwargs["openai_api_base"] = config.base_url
    kwargs["openai_api_key"] = config.api_key

    return OpenAIEmbeddings(**kwargs)


# ---------------------------------------------------------------------------
# Provider 注册表
# ---------------------------------------------------------------------------
# 键：Provider 名称（小写）
# 值：工厂函数 (EmbeddingConfig) -> Embeddings

PROVIDERS: dict[str, callable] = {
    "huggingface": _create_huggingface,
    "ollama": _create_ollama,
    "openai-compatible": _create_openai_compatible,
}
