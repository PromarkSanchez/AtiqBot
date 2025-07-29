# app/crud/crud_document_source.py
import json # Para convertir el dict de credenciales a string JSON antes de encriptar
from typing import Optional, List, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession # type: ignore
from sqlalchemy.future import select # type: ignore

from app.models.document_source_config import DocumentSourceConfig as DocSourceModel
from app.schemas.schemas import DocumentSourceCreate, DocumentSourceUpdate
from app.utils.security_utils import encrypt_data, decrypt_data # type: ignore # Para credenciales

async def create_document_source(db: AsyncSession, source_in: DocumentSourceCreate) -> DocSourceModel:
    encrypted_creds_str = None
    if source_in.credentials_info:
        # Convertir el dict de credenciales a un string JSON para encriptarlo
        credentials_json_str = json.dumps(source_in.credentials_info)
        encrypted_creds_str = encrypt_data(credentials_json_str)
    
    db_source_obj = DocSourceModel(
        name=source_in.name,
        description=source_in.description,
        source_type=source_in.source_type,
        path_or_config=source_in.path_or_config, # Se guarda como JSON directamente
        credentials_info_encrypted=encrypted_creds_str,
        sync_frequency_cron=source_in.sync_frequency_cron
    )
    db.add(db_source_obj)
    await db.commit()
    await db.refresh(db_source_obj)
    return db_source_obj

async def get_document_source_by_id(db: AsyncSession, source_id: int) -> Optional[DocSourceModel]:
    result = await db.execute(select(DocSourceModel).filter(DocSourceModel.id == source_id))
    return result.scalars().first()

async def get_document_source_by_name(db: AsyncSession, name: str) -> Optional[DocSourceModel]:
    result = await db.execute(select(DocSourceModel).filter(DocSourceModel.name == name))
    return result.scalars().first()
    
async def get_document_sources(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[DocSourceModel]:
    result = await db.execute(select(DocSourceModel).offset(skip).limit(limit))
    return result.scalars().all()

async def update_document_source(
    db: AsyncSession, 
    db_source_obj: DocSourceModel,
    source_in: DocumentSourceUpdate
) -> DocSourceModel:
    update_data = source_in.model_dump(exclude_unset=True)

    if "credentials_info" in update_data and update_data["credentials_info"] is not None:
        credentials_json_str = json.dumps(update_data["credentials_info"])
        update_data["credentials_info_encrypted"] = encrypt_data(credentials_json_str)
        del update_data["credentials_info"] # No guardar el dict en texto plano
    elif "credentials_info" in update_data and update_data["credentials_info"] is None:
        # Si se quiere borrar las credenciales explícitamente
        # db_source_obj.credentials_info_encrypted = None # O dejar que no se actualice
        # Por ahora, si es None, no lo cambiamos, para no borrar por error.
        # Si quisieras "borrar", el update debería enviar un dict vacío o una señal específica.
        del update_data["credentials_info"] 


    for field, value in update_data.items():
        setattr(db_source_obj, field, value)
    
    db.add(db_source_obj)
    await db.commit()
    await db.refresh(db_source_obj)
    return db_source_obj

async def delete_document_source(db: AsyncSession, source_id: int) -> Optional[DocSourceModel]:
    db_source_obj = await get_document_source_by_id(db, source_id)
    if db_source_obj:
        await db.delete(db_source_obj)
        await db.commit()
        return db_source_obj
    return None

# Helper para obtener credenciales desencriptadas (USO INTERNO CUIDADOSO)
async def get_decrypted_credentials(source_obj: DocSourceModel) -> Optional[Dict[str, str]]: # type: ignore
    if source_obj and source_obj.credentials_info_encrypted:
        try:
            decrypted_json_str = decrypt_data(source_obj.credentials_info_encrypted)
            return json.loads(decrypted_json_str) # Convertir el string JSON de nuevo a dict
        except json.JSONDecodeError:
            print(f"Error al decodificar JSON de credenciales para source ID {source_obj.id}")
            return {"error": "formato_credenciales_corrupto"}
        except Exception as e: # Otro error de desencriptación
            print(f"Error general al desencriptar credenciales para source ID {source_obj.id}: {e}")
            return {"error": "desencriptacion_fallida"}
    return None