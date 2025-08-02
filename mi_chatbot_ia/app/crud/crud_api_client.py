# Archivo: mi_chatbot_ia/app/crud/crud_api_client.py

import secrets
import json
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.api_client import ApiClient as ApiClientModel
from app.models.context_definition import ContextDefinition as ContextDefinitionModel
from app.schemas.schemas import (
    ApiClientCreate, 
    ApiClientUpdate, 
    ApiClientSettingsSchema,
    ContextDefinitionBriefForApiClient,
    WebchatUIConfig
)

def generate_api_key() -> str:
    """Genera una nueva API Key segura."""
    return secrets.token_urlsafe(32)

def hash_api_key(api_key: str) -> str:
    """Función de hash para la API Key. REEMPLAZAR con algo seguro como bcrypt en producción."""
    return f"hashed_placeholder_{api_key}" 

async def _prepare_api_client_object_for_response(db: AsyncSession, client_orm_obj: ApiClientModel) -> ApiClientModel:
    """Puebla los campos transitorios del objeto ORM antes de enviarlo como respuesta."""
    settings_dict = client_orm_obj.settings if isinstance(client_orm_obj.settings, dict) else {}
    
    try:
        validated_settings = ApiClientSettingsSchema.model_validate(settings_dict)
        context_ids = validated_settings.allowed_context_ids or []
    except Exception:
        context_ids = []

    if context_ids:
        stmt = select(ContextDefinitionModel).filter(ContextDefinitionModel.id.in_(context_ids))
        contexts = (await db.execute(stmt)).scalars().all()
        # model_validate se asegura de convertir el objeto ORM al schema Pydantic correcto
        validated_contexts = [ContextDefinitionBriefForApiClient.model_validate(ctx) for ctx in contexts]
        setattr(client_orm_obj, 'allowed_contexts_details', validated_contexts)
    else:
        setattr(client_orm_obj, 'allowed_contexts_details', [])
        
    return client_orm_obj

async def get_api_client_by_name(db: AsyncSession, name: str) -> Optional[ApiClientModel]:
    result = await db.execute(select(ApiClientModel).filter(ApiClientModel.name == name))
    return result.scalars().first()

async def get_api_client_by_id(db: AsyncSession, api_client_id: int) -> Optional[ApiClientModel]:
    result = await db.execute(select(ApiClientModel).filter(ApiClientModel.id == api_client_id))
    db_api_client = result.scalars().first()
    if db_api_client:
        return await _prepare_api_client_object_for_response(db, db_api_client)
    return None

async def get_api_clients(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[ApiClientModel]:
    stmt = select(ApiClientModel).offset(skip).limit(limit).order_by(ApiClientModel.name)
    clients_from_db = (await db.execute(stmt)).scalars().all()
    
    prepared_clients = [await _prepare_api_client_object_for_response(db, client) for client in clients_from_db]
    return prepared_clients

async def get_api_client_by_hashed_key(db: AsyncSession, hashed_api_key: str) -> Optional[ApiClientModel]:
    stmt = select(ApiClientModel).filter(ApiClientModel.hashed_api_key == hashed_api_key)
    result = await db.execute(stmt)
    db_api_client = result.scalars().first()
    if db_api_client:
        return await _prepare_api_client_object_for_response(db, db_api_client)
    return None

async def create_api_client(db: AsyncSession, api_client_in: ApiClientCreate) -> ApiClientModel:
    plain_text_api_key = generate_api_key()
    hashed_api_key = hash_api_key(plain_text_api_key)
    settings_dict = api_client_in.settings.model_dump() if api_client_in.settings else {}
    
    db_api_client = ApiClientModel(
        name=api_client_in.name,
        hashed_api_key=hashed_api_key,
        description=api_client_in.description,
        is_active=api_client_in.is_active,
        settings=settings_dict
    )
    db.add(db_api_client)
    await db.commit()
    await db.refresh(db_api_client)
    
    setattr(db_api_client, 'api_key_plain', plain_text_api_key) 
    return await _prepare_api_client_object_for_response(db, db_api_client)

async def update_api_client(db: AsyncSession, db_api_client_orm: ApiClientModel, api_client_in: ApiClientUpdate) -> ApiClientModel:
    update_data_dict = api_client_in.model_dump(exclude_unset=True)
    for field_name, new_value in update_data_dict.items():
        if field_name == "settings" and isinstance(new_value, ApiClientSettingsSchema):
            setattr(db_api_client_orm, field_name, new_value.model_dump(mode='json', exclude_none=True))
        else:
            setattr(db_api_client_orm, field_name, new_value)
    await db.commit()
    await db.refresh(db_api_client_orm)
    return await _prepare_api_client_object_for_response(db, db_api_client_orm)

async def regenerate_api_key(db: AsyncSession, db_api_client_orm: ApiClientModel) -> ApiClientModel:
    new_plain_text_key = generate_api_key()
    db_api_client_orm.hashed_api_key = hash_api_key(new_plain_text_key)
    await db.commit()
    await db.refresh(db_api_client_orm)
    setattr(db_api_client_orm, 'api_key_plain', new_plain_text_key)
    return await _prepare_api_client_object_for_response(db, db_api_client_orm)

async def delete_api_client(db: AsyncSession, api_client_id: int) -> Optional[ApiClientModel]:
    db_api_client = await db.get(ApiClientModel, api_client_id)
    if db_api_client:
        await db.delete(db_api_client)
        await db.commit()
        return db_api_client 
    return None

async def update_api_client_webchat_config(db: AsyncSession, api_client_id: int, config_in: WebchatUIConfig) -> Optional[ApiClientModel]:
    db_api_client = await db.get(ApiClientModel, api_client_id)
    if not db_api_client:
        return None
    db_api_client.webchat_ui_config = config_in.model_dump(mode='json')
    await db.commit()
    await db.refresh(db_api_client)
    return await _prepare_api_client_object_for_response(db, db_api_client)