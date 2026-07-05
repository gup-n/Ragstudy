"""Chat LLM configuration CRUD.

LLM API keys use the same Fernet key as Embedding API keys, so runtime secrets stay
encrypted in the local SQLite database.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import exists, func, select, update
from sqlalchemy.orm import Session

from embedding.crud import decrypt_api_key, encrypt_api_key
from llm.models import LLMConfigModel
from llm.schema import LLMConfigCreate, LLMConfigRead, LLMConfigUpdate

logger = logging.getLogger(__name__)


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
        logger.exception("Invalid LLM extra JSON.")
        raise


def _orm_to_read(orm_row: LLMConfigModel) -> LLMConfigRead:
    return LLMConfigRead(
        id=orm_row.id,
        provider=orm_row.provider,
        model=orm_row.model,
        base_url=orm_row.base_url,
        api_key=decrypt_api_key(orm_row.api_key),
        temperature=orm_row.temperature,
        timeout=orm_row.timeout,
        enabled=orm_row.enabled,
        extra=_load_extra(orm_row.extra),
        created_at=orm_row.created_at,
        updated_at=orm_row.updated_at,
    )


def _apply_create_to_orm(create_data: LLMConfigCreate, orm_row: LLMConfigModel) -> None:
    orm_row.provider = create_data.provider
    orm_row.model = create_data.model
    orm_row.base_url = create_data.base_url
    orm_row.api_key = encrypt_api_key(create_data.api_key)
    orm_row.temperature = create_data.temperature
    orm_row.timeout = create_data.timeout
    orm_row.enabled = create_data.enabled
    orm_row.extra = _dump_extra(create_data.extra)


def _apply_update_to_orm(update_data: LLMConfigUpdate, orm_row: LLMConfigModel) -> None:
    fields_set = update_data.model_fields_set

    if "provider" in fields_set and update_data.provider is not None:
        orm_row.provider = update_data.provider
    if "model" in fields_set and update_data.model is not None:
        orm_row.model = update_data.model
    if "base_url" in fields_set:
        orm_row.base_url = update_data.base_url
    if "api_key" in fields_set:
        orm_row.api_key = encrypt_api_key(update_data.api_key)
    if "temperature" in fields_set and update_data.temperature is not None:
        orm_row.temperature = update_data.temperature
    if "timeout" in fields_set:
        orm_row.timeout = update_data.timeout
    if "enabled" in fields_set and update_data.enabled is not None:
        orm_row.enabled = update_data.enabled
    if "extra" in fields_set:
        orm_row.extra = _dump_extra(update_data.extra)


def _disable_other_configs(session: Session, exclude_id: int | None = None) -> None:
    stmt = (
        update(LLMConfigModel)
        .where(LLMConfigModel.enabled.is_(True))
        .values(enabled=False, updated_at=func.now())
    )
    if exclude_id is not None:
        stmt = stmt.where(LLMConfigModel.id != exclude_id)
    session.execute(stmt)


def _get_enabled_row(session: Session) -> LLMConfigModel | None:
    stmt = select(LLMConfigModel).where(LLMConfigModel.enabled.is_(True)).limit(1)
    return session.scalars(stmt).first()


def create_config(session: Session, config_in: LLMConfigCreate) -> LLMConfigRead:
    if config_in.enabled:
        _disable_other_configs(session)

    orm_row = LLMConfigModel()
    _apply_create_to_orm(config_in, orm_row)
    session.add(orm_row)
    session.flush()
    return _orm_to_read(orm_row)


def update_config(
    session: Session, config_id: int, config_in: LLMConfigUpdate
) -> LLMConfigRead:
    orm_row = session.get(LLMConfigModel, config_id)
    if orm_row is None:
        raise ValueError(f"LLM config with id {config_id} not found.")

    _apply_update_to_orm(config_in, orm_row)
    if config_in.enabled is True:
        _disable_other_configs(session, exclude_id=config_id)

    orm_row.updated_at = datetime.now(timezone.utc)
    session.flush()
    return _orm_to_read(orm_row)


def get_config(session: Session, config_id: int) -> LLMConfigRead | None:
    orm_row = session.get(LLMConfigModel, config_id)
    return _orm_to_read(orm_row) if orm_row else None


def list_configs(session: Session) -> list[LLMConfigRead]:
    rows = session.scalars(select(LLMConfigModel)).all()
    return [_orm_to_read(row) for row in rows]


def set_enabled(session: Session, config_id: int, enabled: bool) -> LLMConfigRead:
    orm_row = session.get(LLMConfigModel, config_id)
    if orm_row is None:
        raise ValueError(f"LLM config with id {config_id} not found.")

    if enabled:
        _disable_other_configs(session, exclude_id=config_id)

    orm_row.enabled = enabled
    orm_row.updated_at = datetime.now(timezone.utc)
    session.flush()
    return _orm_to_read(orm_row)


def has_enabled_config(session: Session) -> bool:
    stmt = select(exists().where(LLMConfigModel.enabled.is_(True)))
    return bool(session.scalar(stmt))


def save_config(config_in: LLMConfigCreate) -> LLMConfigRead:
    from embedding.database import get_session

    with get_session() as session:
        return create_config(session, config_in)


def get_enabled_config() -> LLMConfigRead | None:
    from embedding.database import get_session

    with get_session() as session:
        row = _get_enabled_row(session)
        return _orm_to_read(row) if row else None


def delete_config(config_id: int) -> bool:
    from embedding.database import get_session

    with get_session() as session:
        return _delete_config(session, config_id)


def _delete_config(session: Session, config_id: int) -> bool:
    orm_row = session.get(LLMConfigModel, config_id)
    if orm_row is None:
        return False
    session.delete(orm_row)
    session.flush()
    return True
