"""数据库 CRUD 操作（基于主键 id）。

API Key 在写入时自动加密，读取时自动解密。
支持多条配置，但保证最多只有一个 enabled=True 的启用配置（由数据库部分唯一索引保障）。
所有操作基于主键 id 精确定位记录。

事务管理：CRUD 层不提交事务，由调用方控制（建议使用 with session.begin():）。
内部使用 session.flush() 获取数据库生成的字段（如 id、created_at）。
"""

import json
import logging
from datetime import datetime, timezone
from functools import lru_cache

from cryptography.fernet import Fernet
from sqlalchemy import func, select, update, exists
from sqlalchemy.orm import Session

from embedding.config import ENCRYPTION_KEY_PATH
from embedding.models import EmbeddingConfigModel
from embedding.schema import (
    EmbeddingConfigCreate,
    EmbeddingConfigRead,
    EmbeddingConfigUpdate,
    EncryptionError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 加密工具
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_cipher() -> Fernet:
    return Fernet(_load_or_create_key())


def _load_or_create_key() -> bytes:
    if ENCRYPTION_KEY_PATH.exists():
        return ENCRYPTION_KEY_PATH.read_bytes()

    ENCRYPTION_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    ENCRYPTION_KEY_PATH.write_bytes(key)
    logger.info("Encryption key created: %s", ENCRYPTION_KEY_PATH)
    return key


# ---------------------------------------------------------------------------
# JSON 工具
# ---------------------------------------------------------------------------


def _dump_extra(extra: dict | None) -> str | None:
    if not extra:
        return None
    return json.dumps(extra, ensure_ascii=False)


def _load_extra(extra: str | None) -> dict | None:
    if not extra:
        return None
    try:
        return json.loads(extra)
    except json.JSONDecodeError:
        logger.exception("Invalid extra JSON.")
        raise


# ---------------------------------------------------------------------------
# API Key 加解密
# ---------------------------------------------------------------------------


def encrypt_api_key(api_key: str | None) -> str | None:
    if not api_key:
        return None
    try:
        return _get_cipher().encrypt(api_key.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        logger.exception("Failed to encrypt API Key.")
        raise EncryptionError("Failed to encrypt API Key.") from exc


def decrypt_api_key(api_key: str | None) -> str | None:
    if not api_key:
        return None
    try:
        return _get_cipher().decrypt(api_key.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        logger.exception("Failed to decrypt API Key.")
        raise EncryptionError("Failed to decrypt API Key.") from exc


# ---------------------------------------------------------------------------
# ORM ←→ Pydantic 转换
# ---------------------------------------------------------------------------


def _orm_to_read(orm_row: EmbeddingConfigModel) -> EmbeddingConfigRead:
    return EmbeddingConfigRead(
        id=orm_row.id,
        provider=orm_row.provider,
        model=orm_row.model,
        base_url=orm_row.base_url,
        api_key=decrypt_api_key(orm_row.api_key),
        enabled=orm_row.enabled,
        extra=_load_extra(orm_row.extra),
        created_at=orm_row.created_at,
        updated_at=orm_row.updated_at,
    )


def _apply_create_to_orm(
    create_data: EmbeddingConfigCreate, orm_row: EmbeddingConfigModel
) -> None:
    orm_row.provider = create_data.provider
    orm_row.model = create_data.model
    orm_row.base_url = create_data.base_url
    orm_row.api_key = encrypt_api_key(create_data.api_key)
    orm_row.enabled = create_data.enabled
    orm_row.extra = _dump_extra(create_data.extra)


def _apply_update_to_orm(
    update_data: EmbeddingConfigUpdate, orm_row: EmbeddingConfigModel
) -> None:
    """应用更新数据到 ORM 对象，仅更新非 None 字段。"""
    fields_set = update_data.model_fields_set

    if "provider" in fields_set and update_data.provider is not None:
        orm_row.provider = update_data.provider
    if "model" in fields_set and update_data.model is not None:
        orm_row.model = update_data.model
    if "base_url" in fields_set:
        orm_row.base_url = update_data.base_url
    if "api_key" in fields_set:
        orm_row.api_key = encrypt_api_key(update_data.api_key)
    if "enabled" in fields_set and update_data.enabled is not None:
        orm_row.enabled = update_data.enabled
    if "extra" in fields_set:
        orm_row.extra = _dump_extra(update_data.extra)


# ---------------------------------------------------------------------------
# 公共辅助函数
# ---------------------------------------------------------------------------


def _disable_other_configs(session: Session, exclude_id: int | None = None) -> None:
    """禁用除了 exclude_id 之外的所有当前启用的配置，并更新其 updated_at。"""
    stmt = (
        update(EmbeddingConfigModel)
        .where(EmbeddingConfigModel.enabled.is_(True))
        .values(enabled=False, updated_at=func.now())
    )
    if exclude_id is not None:
        stmt = stmt.where(EmbeddingConfigModel.id != exclude_id)
    session.execute(stmt)


def _get_enabled_row(session: Session) -> EmbeddingConfigModel | None:
    """获取当前启用的配置（由于唯一索引，最多一条）。"""
    stmt = (
        select(EmbeddingConfigModel)
        .where(EmbeddingConfigModel.enabled.is_(True))
        .limit(1)
    )
    return session.scalars(stmt).first()


# ---------------------------------------------------------------------------
# 公开 CRUD（事务由调用方管理）
# ---------------------------------------------------------------------------


def create_config(
    session: Session, config_in: EmbeddingConfigCreate
) -> EmbeddingConfigRead:
    if config_in.enabled:
        _disable_other_configs(session)

    orm_row = EmbeddingConfigModel()
    _apply_create_to_orm(config_in, orm_row)

    session.add(orm_row)
    session.flush()
    return _orm_to_read(orm_row)


def update_config(
    session: Session, config_id: int, config_in: EmbeddingConfigUpdate
) -> EmbeddingConfigRead:
    orm_row = session.get(EmbeddingConfigModel, config_id)
    if orm_row is None:
        raise ValueError(f"Config with id {config_id} not found.")

    _apply_update_to_orm(config_in, orm_row)

    if config_in.enabled is True:
        _disable_other_configs(session, exclude_id=config_id)

    # 所有修改完成后，显式更新时间戳
    orm_row.updated_at = datetime.now(timezone.utc)
    session.flush()
    return _orm_to_read(orm_row)


def get_config(session: Session, config_id: int) -> EmbeddingConfigRead | None:
    orm_row = session.get(EmbeddingConfigModel, config_id)
    return _orm_to_read(orm_row) if orm_row else None


def list_configs(session: Session) -> list[EmbeddingConfigRead]:
    stmt = select(EmbeddingConfigModel)
    rows = session.scalars(stmt).all()
    return [_orm_to_read(row) for row in rows]


def set_enabled(session: Session, config_id: int, enabled: bool) -> EmbeddingConfigRead:
    orm_row = session.get(EmbeddingConfigModel, config_id)
    if orm_row is None:
        raise ValueError(f"Config with id {config_id} not found.")

    if enabled:
        _disable_other_configs(session, exclude_id=config_id)

    orm_row.enabled = enabled
    orm_row.updated_at = datetime.now(timezone.utc)
    session.flush()
    return _orm_to_read(orm_row)


def has_enabled_config(session: Session) -> bool:
    """使用 EXISTS 快速检查是否有启用配置。"""
    stmt = select(exists().where(EmbeddingConfigModel.enabled.is_(True)))
    return bool(session.scalar(stmt))


# ---------------------------------------------------------------------------
# 便捷包装函数（自动管理 Session，供 embedding/__init__.py 导出）
# ---------------------------------------------------------------------------


def save_config(config_in: EmbeddingConfigCreate) -> EmbeddingConfigRead:
    """保存配置（自动管理 Session）。

    Args:
        config_in: 待创建的配置对象。

    Returns:
        创建后的配置（含数据库生成的 id / created_at）。
    """
    from embedding.database import get_session

    with get_session() as session:
        return create_config(session, config_in)


def get_enabled_config() -> EmbeddingConfigRead | None:
    """获取当前启用的配置（自动管理 Session）。"""
    from embedding.database import get_session

    with get_session() as session:
        row = _get_enabled_row(session)
        return _orm_to_read(row) if row else None


def delete_config(config_id: int) -> bool:
    """删除配置（自动管理 Session）。"""
    from embedding.database import get_session

    with get_session() as session:
        return _delete_config(session, config_id)


def _delete_config(session: Session, config_id: int) -> bool:
    """内部：删除配置（需外部管理 Session）。"""
    orm_row = session.get(EmbeddingConfigModel, config_id)
    if orm_row is None:
        return False
    session.delete(orm_row)
    session.flush()
    return True
