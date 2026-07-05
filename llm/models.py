from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, Text, func, true
from sqlalchemy.orm import Mapped, mapped_column

from embedding.models import Base


class LLMConfigModel(Base):
    __tablename__ = "llm_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    timeout: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


Index(
    "ix_unique_llm_enabled_true",
    LLMConfigModel.enabled,
    unique=True,
    postgresql_where=LLMConfigModel.enabled.is_(true()),
    sqlite_where=LLMConfigModel.enabled.is_(true()),
)
