"""Chat LLM factory."""

from typing import Any

from llm.providers import PROVIDERS
from llm.schema import LLMConfig, ProviderNotFoundError


def create_chat_model(config: LLMConfig) -> Any:
    provider = config.provider.lower()
    factory = PROVIDERS.get(provider)
    if factory is None:
        raise ProviderNotFoundError(config.provider)
    return factory(config)
