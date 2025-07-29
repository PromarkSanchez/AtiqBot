# app/crud/crud_api_client.py
import secrets
import json
from typing import Optional, List, Dict, Any, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload # Puede ser útil para optimizar carga de relaciones

from app.models.api_client import ApiClient as ApiClientModel
from app.models.context_definition import ContextDefinition as ContextDefinitionModel
from app.schemas.schemas import (
    ApiClientCreate, 
    ApiClientUpdate, 
    ApiClientSettingsSchema, # Usado para validar/parsear settings
    ContextDefinitionBriefForApiClient,
)

# --- Funciones de Hashing y Generación de Clave (Placeholder - Implementar de forma segura) ---
def generate_api_key() -> str:
    return secrets.token_urlsafe(32)

def hash_api_key(api_key: str) -> str: # TODO: Implementar hashing real (ej. bcrypt)
    print("CRUD WARNING: Usando hashing de API Key placeholder (INSEGURO).")
    return f"hashed__{api_key}__placeholder" 

# def verify_api_key(plain_api_key: str, hashed_api_key: str) -> bool: # TODO: Implementar
#     return f"hashed__{plain_api_key}__placeholder" == hashed_api_key

async def _prepare_api_client_for_response(db: AsyncSession, client_orm: ApiClientModel) -> ApiClientModel:
    """
    Toma un objeto de la BD y le añade los detalles de los contextos.
    Esta función es necesaria porque no hay una relación directa en SQLAlchemy.
    """
    settings_dict = client_orm.settings or {}
    context_ids = settings_dict.get("allowed_context_ids", [])
    
    if context_ids:
        stmt = select(ContextDefinitionModel).filter(ContextDefinitionModel.id.in_(context_ids))
        contexts = (await db.execute(stmt)).scalars().all()
        setattr(client_orm, 'allowed_contexts_details', contexts)
    else:
        setattr(client_orm, 'allowed_contexts_details', [])
        
    return client_orm
async def _prepare_api_client_object_for_response(
    db: AsyncSession, client_orm_obj: ApiClientModel
) -> ApiClientModel:
    """
    Prepara un objeto ApiClientModel ORM para ser usado por schemas Pydantic de respuesta.
    - NO MODIFICA client_orm_obj.settings. Pydantic se encarga de validar/parsear 
      el dict de client_orm_obj.settings al construir el schema de respuesta.
    - Puebla el atributo transitorio 'allowed_contexts_details'.
    - Los atributos como 'api_key_plain' son añadidos externamente si es necesario.
    """
    
    settings_from_db_dict: Dict[str, Any] = {}
    if isinstance(client_orm_obj.settings, dict):
        settings_from_db_dict = client_orm_obj.settings
    elif isinstance(client_orm_obj.settings, str): # Fallback si es string JSON
        try:
            settings_from_db_dict = json.loads(client_orm_obj.settings)
        except json.JSONDecodeError:
            print(f"CRUD WARNING (_prepare) (ApiClient ID {client_orm_obj.id}): settings string JSON inválido.")
    
    # Validamos los settings para la lógica interna de este método (ej. obtener IDs de contexto)
    # pero NO reasignamos esto a client_orm_obj.settings.
    temp_parsed_settings_for_logic: ApiClientSettingsSchema
    try:
        temp_parsed_settings_for_logic = ApiClientSettingsSchema.model_validate(settings_from_db_dict)
    except Exception as e:
        print(f"CRUD WARNING (_prepare) (ApiClient ID {client_orm_obj.id}): Error validando settings desde BD: {e}. Usando defaults para obtener allowed_contexts.")
        # Proveer un application_id válido es crucial si el schema lo requiere y los datos están mal
        temp_parsed_settings_for_logic = ApiClientSettingsSchema(application_id=f"temp_default_client_{client_orm_obj.id}") 
    
    # Poblar 'allowed_contexts_details' (como atributo transitorio)
    allowed_context_ids = temp_parsed_settings_for_logic.allowed_context_ids or []
    
    if allowed_context_ids:
        stmt_contexts = select(ContextDefinitionModel).filter(ContextDefinitionModel.id.in_(allowed_context_ids))
        result_contexts = await db.execute(stmt_contexts)
        contexts_orm_list = result_contexts.scalars().all()
        
        contexts_pydantic_list = [ContextDefinitionBriefForApiClient.model_validate(ctx) for ctx in contexts_orm_list]
        setattr(client_orm_obj, 'allowed_contexts_details', contexts_pydantic_list) # Correcto, este es transitorio y tiene el nombre del campo en el schema Pydantic
    else:
        setattr(client_orm_obj, 'allowed_contexts_details', [])
        
    return client_orm_obj

async def get_api_client_by_name(db: AsyncSession, name: str) -> Optional[ApiClientModel]:
    result = await db.execute(select(ApiClientModel).filter(ApiClientModel.name == name))
    db_api_client = result.scalars().first()
    # (Si quisieras optimizar esta, usarías la misma lógica que get_by_id)
    return db_api_client

async def get_api_client_by_id(db: AsyncSession, api_client_id: int) -> Optional[ApiClientModel]:
    """
    Obtiene un cliente y enriquece sus detalles de contexto en una segunda consulta eficiente.
    """
    # Primera consulta: obtener el cliente
    result = await db.execute(select(ApiClientModel).filter(ApiClientModel.id == api_client_id))
    db_api_client = result.scalars().first()
    
    if db_api_client and db_api_client.settings and db_api_client.settings.get("allowed_context_ids"):
        # Segunda consulta: obtener los detalles de sus contextos
        context_ids = db_api_client.settings["allowed_context_ids"]
        stmt_contexts = select(ContextDefinitionModel).filter(ContextDefinitionModel.id.in_(context_ids))
        contexts_result = await db.execute(stmt_contexts)
        # Asignamos el atributo transitorio que Pydantic espera
        setattr(db_api_client, 'allowed_contexts_details', contexts_result.scalars().all())
    elif db_api_client:
        setattr(db_api_client, 'allowed_contexts_details', [])
        
    return db_api_client

async def get_api_clients(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[ApiClientModel]:
    """Obtiene una lista de clientes y enriquece cada uno con los detalles de sus contextos."""
    stmt = select(ApiClientModel).offset(skip).limit(limit).order_by(ApiClientModel.name)
    clients_from_db = (await db.execute(stmt)).scalars().all()
    
    # Preparamos cada cliente para la respuesta, uno por uno
    prepared_clients = [await _prepare_api_client_for_response(db, client) for client in clients_from_db]
    return prepared_clients


async def get_api_client_by_id(db: AsyncSession, api_client_id: int) -> Optional[ApiClientModel]:
    db_client = await db.get(ApiClientModel, api_client_id)
    if db_client:
        return await _prepare_api_client_for_response(db, db_client)
    return None

async def get_api_client_by_hashed_key(db: AsyncSession, hashed_api_key: str) -> Optional[ApiClientModel]:
    stmt = select(ApiClientModel).filter(ApiClientModel.hashed_api_key == hashed_api_key)
    result = await db.execute(stmt) # Agregado await
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
    # Devolvemos el cliente "completo"
    return await get_api_client_by_id(db, db_api_client.id)


async def update_api_client(
    db: AsyncSession, 
    db_api_client_orm: ApiClientModel, # Objeto ORM existente
    api_client_in: ApiClientUpdate      # Schema Pydantic con datos de actualización
) -> ApiClientModel:
    
    # Obtener un dict solo con los campos que realmente se enviaron para actualizar
    update_data_dict = api_client_in.model_dump(exclude_unset=True)

    for field_name, new_value in update_data_dict.items():
        if field_name == "settings":
            # Si 'settings' se envía, new_value es ApiClientSettingsSchema (del tipo en ApiClientUpdate)
            # Necesitamos convertirlo a dict para guardar en la columna JSONB
            if isinstance(new_value, ApiClientSettingsSchema):
                setattr(db_api_client_orm, field_name, new_value.model_dump(mode='json', exclude_none=True))
            elif isinstance(new_value, dict): # Si por alguna razón ya es un dict
                 setattr(db_api_client_orm, field_name, new_value)
            # Si new_value es None y settings es opcional, se manejará por exclude_none
        else: # Para otros campos como name, description, is_active
            setattr(db_api_client_orm, field_name, new_value)
    
    # db.add(db_api_client_orm) # SQLAlchemy rastrea cambios en objetos ya en sesión
    await db.commit()
    await db.refresh(db_api_client_orm)
        
    return await _prepare_api_client_object_for_response(db, db_api_client_orm)

        
async def regenerate_api_key(db: AsyncSession, db_api_client_orm: ApiClientModel) -> ApiClientModel:
    new_plain_text_key = generate_api_key()
    db_api_client_orm.hashed_api_key = hash_api_key(new_plain_text_key)
    
    # `updated_at` se actualizará automáticamente si usas onupdate=now() en el modelo
    await db.commit()
    await db.refresh(db_api_client_orm)
    
    # Añadir atributo transitorio para la respuesta
    setattr(db_api_client_orm, 'api_key_plain', new_plain_text_key)
    
    return await _prepare_api_client_object_for_response(db, db_api_client_orm)

async def delete_api_client(db: AsyncSession, api_client_id: int) -> Optional[ApiClientModel]:
    db_api_client = await db.get(ApiClientModel, api_client_id) # Usar db.get()
    if db_api_client:
        await db.delete(db_api_client)
        await db.commit()
        # Retornar el objeto justo antes de ser eliminado, sin _prepare_
        # ya que la respuesta del endpoint es 204 No Content o un mensaje simple.
        return db_api_client 
    return None