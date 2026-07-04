import pytest
from pydantic import ValidationError

from embedding.schema import EmbeddingConfigCreate


def test_embedding_config_rejects_empty_model():
    with pytest.raises(ValidationError):
        EmbeddingConfigCreate(provider="huggingface", model=" ")


def test_embedding_config_accepts_supported_provider():
    config = EmbeddingConfigCreate(
        provider="openai-compatible",
        model="text-embedding-3-small",
        base_url="https://api.openai.com/v1",
        api_key=" sk-test ",
    )

    assert config.api_key == "sk-test"
