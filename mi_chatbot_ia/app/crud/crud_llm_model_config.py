# app/crud/crud_llm_model_config.py

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# Tus importaciones originales están perfectas
from app.models.llm_model_config import LLMModelConfig as LLMModelConfigModel
from app.schemas.schemas import LLMModelConfigCreate, LLMModelConfigUpdate
from app.utils.security_utils import encrypt_data as encrypt_value

async def create_llm_model_config(db: AsyncSession, *, model_in: LLMModelConfigCreate) -> LLMModelConfigModel:
    model_data = model_in.model_dump(exclude={'api_key_plain'})
    
    # Tu lógica original para encriptar la api_key principal
    if model_in.api_key_plain:
        model_data['api_key_encrypted'] = encrypt_value(model_in.api_key_plain)

    # === INICIO DE LA NUEVA LÓGICA: Encriptación dentro de config_json ===
    # Revisamos si config_json existe y es un diccionario
    if 'config_json' in model_data and isinstance(model_data.get('config_json'), dict):
        # Creamos una copia para trabajar de forma segura
        config_json = model_data['config_json'].copy()
        
        # Si el frontend envía 'aws_access_key_id', lo encriptamos
        if config_json.get('aws_access_key_id'):
            # Guardamos la versión encriptada usando tu alias 'encrypt_value'
            config_json['aws_access_key_id_encrypted'] = encrypt_value(config_json['aws_access_key_id'])
            # Eliminamos la clave en texto plano del diccionario
            del config_json['aws_access_key_id']
        
        # Hacemos lo mismo para la clave secreta
        if config_json.get('aws_secret_access_key'):
            config_json['aws_secret_access_key_encrypted'] = encrypt_value(config_json['aws_secret_access_key'])
            del config_json['aws_secret_access_key']
        
        # Reemplazamos el config_json original con la versión modificada y segura
        model_data['config_json'] = config_json
    # === FIN DE LA NUEVA LÓGICA ===

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

async def get_llm_model_configs(db: AsyncSession, skip: int = 0, limit: int = 100, only_active: Optional[bool] = None) -> List[LLMModelConfigModel]:
    stmt = select(LLMModelConfigModel)
    if only_active is not None:
        stmt = stmt.filter(LLMModelConfigModel.is_active == only_active)
    stmt = stmt.order_by(LLMModelConfigModel.provider, LLMModelConfigModel.display_name).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

async def update_llm_model_config(db: AsyncSession, *, db_model: LLMModelConfigModel, model_in: LLMModelConfigUpdate) -> LLMModelConfigModel:
    update_data = model_in.model_dump(exclude_unset=True, exclude={'api_key_plain'})
    
    # Tu lógica original para la api_key principal
    if model_in.api_key_plain:
        update_data['api_key_encrypted'] = encrypt_value(model_in.api_key_plain)
    
    # === INICIO DE LA NUEVA LÓGICA: Encriptación dentro de config_json al ACTUALIZAR ===
    if 'config_json' in update_data and isinstance(update_data.get('config_json'), dict):
        config_json = update_data['config_json'].copy()
        
        if config_json.get('aws_access_key_id'):
            config_json['aws_access_key_id_encrypted'] = encrypt_value(config_json['aws_access_key_id'])
            del config_json['aws_access_key_id']
        
        if config_json.get('aws_secret_access_key'):
            config_json['aws_secret_access_key_encrypted'] = encrypt_value(config_json['aws_secret_access_key'])
            del config_json['aws_secret_access_key']
        
        # Fusionamos el JSON existente con el nuevo para no perder claves antiguas no modificadas
        # Por ejemplo, si solo se actualiza la región, mantenemos las claves encriptadas.
        if db_model.config_json:
            merged_json = db_model.config_json.copy()
            merged_json.update(config_json)
            update_data['config_json'] = merged_json
        else:
            update_data['config_json'] = config_json
    # === FIN DE LA NUEVA LÓGICA ===
    
    for field, value in update_data.items():
        setattr(db_model, field, value)
        
    db.add(db_model)
    await db.commit()
    await db.refresh(db_model)
    return db_model

async def delete_llm_model_config(db: AsyncSession, model_id: int) -> bool:
    db_model = await get_llm_model_config_by_id(db, model_id)
    if db_model:
        await db.delete(db_model)
        await db.commit()
        return True
    return False