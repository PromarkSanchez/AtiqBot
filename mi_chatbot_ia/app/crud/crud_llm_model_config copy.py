# app/crud/crud_llm_model_config.py

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.llm_model_config import LLMModelConfig as LLMModelConfigModel
# [REFACTOR] Importamos los nuevos schemas del paso anterior
from app.schemas.schemas import LLMModelConfigCreate, LLMModelConfigUpdate
# [REFACTOR] Importamos el servicio de encriptación que ya tienes
from app.utils.security_utils import encrypt_data   as encrypt_value


async def create_llm_model_config(db: AsyncSession, *, model_in: LLMModelConfigCreate) -> LLMModelConfigModel:
    """
    Crea una nueva configuración de modelo LLM, encriptando la API key si se proporciona.
    """
    # Excluimos api_key_plain porque no es un campo del modelo SQLAlchemy.
    model_data = model_in.model_dump(exclude={'api_key_plain'})
    
    # [REFACTOR] Lógica de encriptación
    if model_in.api_key_plain:
        print(f"CRUD_LLM_CONFIG: Encriptando API key para el nuevo modelo '{model_in.display_name}'.")
        model_data['api_key_encrypted'] = encrypt_value(model_in.api_key_plain)

    db_model = LLMModelConfigModel(**model_data)
    db.add(db_model)
    await db.commit()
    await db.refresh(db_model)
    return db_model


async def get_llm_model_config_by_id(db: AsyncSession, model_id: int) -> Optional[LLMModelConfigModel]:
    result = await db.execute(select(LLMModelConfigModel).filter(LLMModelConfigModel.id == model_id))
    return result.scalars().first()


async def get_llm_model_config_by_identifier(db: AsyncSession, identifier: str) -> Optional[LLMModelConfigModel]:
    result = await db.execute(select(LLMModelConfigModel).filter(LLMModelConfigModel.model_identifier == identifier))
    return result.scalars().first()


async def get_llm_model_configs(db: AsyncSession, skip: int = 0, limit: int = 100, only_active: bool = False) -> List[LLMModelConfigModel]:
    stmt = select(LLMModelConfigModel)
    if only_active:
        stmt = stmt.filter(LLMModelConfigModel.is_active == True)
    stmt = stmt.order_by(LLMModelConfigModel.provider, LLMModelConfigModel.display_name).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def update_llm_model_config(
    db: AsyncSession, 
    *,
    db_model: LLMModelConfigModel, 
    model_in: LLMModelConfigUpdate
) -> LLMModelConfigModel:
    """
    Actualiza una configuración de modelo LLM existente. Si se proporciona una nueva
    api_key_plain, la encripta y reemplaza la anterior.
    """
    # Obtenemos los datos del schema, excluyendo los no seteados y el campo transitorio.
    update_data = model_in.model_dump(exclude_unset=True, exclude={'api_key_plain'})
    
    # [REFACTOR] Lógica de encriptación para la actualización
    # Si el usuario envió una nueva clave en el formulario, la encriptamos.
    if model_in.api_key_plain:
        print(f"CRUD_LLM_CONFIG: Encriptando y actualizando API key para el modelo ID {db_model.id}.")
        update_data['api_key_encrypted'] = encrypt_value(model_in.api_key_plain)
    
    for field, value in update_data.items():
        setattr(db_model, field, value)
        
    db.add(db_model)
    await db.commit()
    await db.refresh(db_model)
    return db_model


async def delete_llm_model_config(db: AsyncSession, model_id: int) -> Optional[LLMModelConfigModel]:
    db_model = await get_llm_model_config_by_id(db, model_id)
    if db_model:
        await db.delete(db_model)
        await db.commit()
        return db_model
    return None