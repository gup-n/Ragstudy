from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator


ProviderName = Literal["ollama", "openai-compatible"]


class LLMConfigBase(BaseModel):
    provider: ProviderName
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    temperature: float = 0.2
    timeout: Optional[float] = 60.0
    extra: Optional[dict[str, Any]] = None

    @field_validator("model")
    @classmethod
    def clean_model(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("model 不能为空")
        return stripped

    @field_validator("api_key")
    @classmethod
    def clean_api_key(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if v < 0:
            raise ValueError("temperature 不能小于 0")
        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("timeout 必须大于 0")
        return v


class LLMConfigCreate(LLMConfigBase):
    enabled: bool = True


class LLMConfigUpdate(BaseModel):
    provider: Optional[ProviderName] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    temperature: Optional[float] = None
    timeout: Optional[float] = None
    enabled: Optional[bool] = None
    extra: Optional[dict[str, Any]] = None

    @field_validator("model")
    @classmethod
    def clean_model(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("model 不能为空")
        return stripped

    @field_validator("api_key")
    @classmethod
    def clean_api_key(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("temperature 不能小于 0")
        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("timeout 必须大于 0")
        return v


class LLMConfig(LLMConfigBase):
    """Runtime LLM config with api_key already decrypted."""


class LLMConfigRead(LLMConfigBase):
    id: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LLMError(Exception):
    """LLM module base exception."""


class LLMConfigurationError(LLMError):
    """Missing or invalid Chat LLM configuration."""


class ProviderNotFoundError(LLMError):
    """No Chat LLM provider factory is registered for the requested provider."""
