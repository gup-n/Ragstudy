from datetime import datetime

from sqlalchemy import DateTime, String, Text, func, Index, true
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EmbeddingConfigModel(Base):
    __tablename__ = "embedding_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)  # 加密存储
    enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        # 注意：不设置 onupdate，由应用层显式维护
    )


# 部分唯一索引：保证最多一条 enabled=True
# 支持 PostgreSQL 和 SQLite 3.8.0+，使用 SQLAlchemy 表达式，避免 text()
Index(
    "ix_unique_enabled_true",
    EmbeddingConfigModel.enabled,
    unique=True,
    postgresql_where=EmbeddingConfigModel.enabled.is_(true()),
    sqlite_where=EmbeddingConfigModel.enabled.is_(true()),
)
