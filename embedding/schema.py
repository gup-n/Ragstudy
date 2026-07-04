from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class EmbeddingConfigBase(BaseModel):
    provider: str
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    extra: Optional[dict] = None


class EmbeddingConfigCreate(EmbeddingConfigBase):
    enabled: bool = True

    @field_validator("api_key")
    @classmethod
    def clean_api_key(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None


class EmbeddingConfigUpdate(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    enabled: Optional[bool] = None
    extra: Optional[dict] = None

    @field_validator("api_key")
    @classmethod
    def clean_api_key(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None


class EmbeddingConfig(EmbeddingConfigBase):
    """运行时 Embedding 配置（不含 id / 时间戳，api_key 已解密）。

    由 crud.get_enabled_config() 返回的 EmbeddingConfigRead 转换而来，
    供 Factory 创建 Embeddings 实例使用。
    """

    pass


class EmbeddingConfigRead(EmbeddingConfigBase):
    id: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmbeddingError(Exception):
    """Embedding 模块基础异常"""

    pass


class EncryptionError(EmbeddingError):
    """API 密钥加密/解密异常"""

    pass


class ProviderNotFoundError(EmbeddingError):
    """未找到对应的 Embedding Provider"""

    pass


class ModelDownloadError(EmbeddingError):
    """HuggingFace 模型下载失败"""

    pass
