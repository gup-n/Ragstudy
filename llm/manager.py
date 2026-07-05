"""Unified Chat LLM access point."""

import logging
from typing import Any

from embedding.database import init_db
from llm.env import load_config_from_env
from llm.factory import create_chat_model
from llm.schema import LLMConfig

logger = logging.getLogger(__name__)


def _to_runtime_config(config) -> LLMConfig:
    return LLMConfig(
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        api_key=config.api_key,
        temperature=config.temperature,
        timeout=config.timeout,
        extra=config.extra,
    )


def get_chat_model() -> Any | None:
    """Get the enabled Chat LLM from DB, falling back to RAG_LLM_* env vars."""
    init_db()
    from llm.crud import get_enabled_config

    config = get_enabled_config()
    if config is not None:
        logger.info(
            "Loaded LLM config: provider=%s model=%s",
            config.provider,
            config.model,
        )
        return create_chat_model(_to_runtime_config(config))

    env_config = load_config_from_env()
    if env_config is None:
        logger.info("No LLM config found in database or environment.")
        return None

    logger.info(
        "Loaded LLM config from environment: provider=%s model=%s",
        env_config.provider,
        env_config.model,
    )
    return create_chat_model(env_config)
