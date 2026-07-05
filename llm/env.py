"""Optional environment fallback for Chat LLM configuration."""

import os

from dotenv import load_dotenv

from llm.config import (
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    OLLAMA_DEFAULT_BASE_URL,
    OPENAI_COMPATIBLE_DEFAULT_BASE_URL,
)
from llm.schema import LLMConfig, LLMConfigurationError

SUPPORTED_ENV_PROVIDERS = {"openai-compatible", "ollama"}


def _clean_env(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _env_float(name: str, default: float | None) -> float | None:
    raw = _clean_env(os.getenv(name))
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise LLMConfigurationError(f"{name} 必须是数字") from exc


def load_config_from_env(*, load_dotenv_file: bool = True) -> LLMConfig | None:
    """Read RAG_LLM_* variables from .env/environment if no DB config exists."""
    if load_dotenv_file:
        load_dotenv()

    model = _clean_env(os.getenv("RAG_LLM_MODEL"))
    if not model:
        return None

    provider = (_clean_env(os.getenv("RAG_LLM_PROVIDER")) or "openai-compatible").lower()
    if provider not in SUPPORTED_ENV_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_ENV_PROVIDERS))
        raise LLMConfigurationError(
            f"不支持的 RAG_LLM_PROVIDER: {provider}，可选值: {supported}"
        )

    base_url = _clean_env(os.getenv("RAG_LLM_BASE_URL"))
    if provider == "openai-compatible":
        base_url = base_url or OPENAI_COMPATIBLE_DEFAULT_BASE_URL
    elif provider == "ollama":
        base_url = base_url or OLLAMA_DEFAULT_BASE_URL

    return LLMConfig(
        provider=provider,  # type: ignore[arg-type]
        model=model,
        base_url=base_url,
        api_key=_clean_env(os.getenv("RAG_LLM_API_KEY")),
        temperature=_env_float("RAG_LLM_TEMPERATURE", DEFAULT_TEMPERATURE)
        or DEFAULT_TEMPERATURE,
        timeout=_env_float("RAG_LLM_TIMEOUT", DEFAULT_TIMEOUT),
    )
