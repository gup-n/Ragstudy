import pytest
from pydantic import ValidationError

from llm.env import load_config_from_env
from llm.schema import LLMConfigCreate


def test_llm_config_rejects_empty_model():
    with pytest.raises(ValidationError):
        LLMConfigCreate(provider="openai-compatible", model=" ")


def test_llm_config_accepts_local_ollama_model():
    config = LLMConfigCreate(provider="ollama", model="qwen2.5:7b")

    assert config.provider == "ollama"
    assert config.api_key is None


def test_llm_config_strips_api_key():
    config = LLMConfigCreate(
        provider="openai-compatible",
        model="gpt-4o-mini",
        api_key=" test-key ",
    )

    assert config.api_key == "test-key"


def test_llm_env_fallback_requires_model(monkeypatch):
    monkeypatch.delenv("RAG_LLM_MODEL", raising=False)

    assert load_config_from_env(load_dotenv_file=False) is None


def test_llm_env_fallback_loads_openai_compatible(monkeypatch):
    monkeypatch.setenv("RAG_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("RAG_LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("RAG_LLM_API_KEY", " test-key ")

    config = load_config_from_env(load_dotenv_file=False)

    assert config is not None
    assert config.provider == "openai-compatible"
    assert config.model == "gpt-4o-mini"
    assert config.api_key == "test-key"
