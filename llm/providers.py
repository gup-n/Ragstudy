"""Chat LLM provider registry."""

from collections.abc import Callable
from typing import Any

from llm.config import OLLAMA_DEFAULT_BASE_URL, OPENAI_COMPATIBLE_DEFAULT_BASE_URL
from llm.schema import LLMConfig


def _create_openai_compatible(config: LLMConfig) -> Any:
    """Create an OpenAI-compatible chat model."""
    from langchain_openai import ChatOpenAI

    kwargs: dict[str, Any] = dict(config.extra or {})
    kwargs["model"] = config.model
    kwargs["base_url"] = config.base_url or OPENAI_COMPATIBLE_DEFAULT_BASE_URL
    kwargs["temperature"] = config.temperature
    if config.api_key:
        kwargs["api_key"] = config.api_key
    if config.timeout is not None:
        kwargs["timeout"] = config.timeout
    return ChatOpenAI(**kwargs)


def _create_ollama(config: LLMConfig) -> Any:
    """Create a local Ollama chat model."""
    from langchain_ollama import ChatOllama

    kwargs: dict[str, Any] = dict(config.extra or {})
    kwargs["model"] = config.model
    kwargs["base_url"] = config.base_url or OLLAMA_DEFAULT_BASE_URL
    kwargs["temperature"] = config.temperature
    return ChatOllama(**kwargs)


ProviderFactory = Callable[[LLMConfig], Any]

PROVIDERS: dict[str, ProviderFactory] = {
    "openai-compatible": _create_openai_compatible,
    "ollama": _create_ollama,
}
