# app/crud/crud_virtual_agent_profile.py
from typing import Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.virtual_agent_profile import VirtualAgentProfile as VAPModel
from app.models.llm_model_config import LLMModelConfig as LLMModelConfigModel # Para selectinload
from app.schemas.schemas import VirtualAgentProfileCreate, VirtualAgentProfileUpdate # Ajusta desde tu app/schemas.py

async def create_virtual_agent_profile(db: AsyncSession, profile_in: VirtualAgentProfileCreate) -> VAPModel:
    # Validar que llm_model_config_id existe (opcional, la FK de la BD lo hará, pero puede ser bueno aquí)
    # llm_config = await db.get(LLMModelConfigModel, profile_in.llm_model_config_id)
    # if not llm_config:
    #     raise ValueError(f"LLMModelConfig con ID {profile_in.llm_model_config_id} no encontrado.")
        
    db_profile = VAPModel(**profile_in.model_dump())
    db.add(db_profile)
    await db.commit()
    await db.refresh(db_profile)
    # Para que llm_model_config se popule en la respuesta, el get_by_id debe cargarlo
    return await get_virtual_agent_profile_by_id(db, db_profile.id)


async def get_virtual_agent_profile_by_id(db: AsyncSession, profile_id: int, load_relations: bool = True) -> Optional[VAPModel]:
    stmt = select(VAPModel).filter(VAPModel.id == profile_id)
    if load_relations:
        stmt = stmt.options(selectinload(VAPModel.llm_model_config))
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_virtual_agent_profile_by_name(db: AsyncSession, name: str, load_relations: bool = False) -> Optional[VAPModel]:
    stmt = select(VAPModel).filter(VAPModel.name == name)
    if load_relations:
        stmt = stmt.options(selectinload(VAPModel.llm_model_config))
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_virtual_agent_profiles(db: AsyncSession, skip: int = 0, limit: int = 100, only_active: bool = False) -> List[VAPModel]:
    stmt = select(VAPModel).options(selectinload(VAPModel.llm_model_config)) # Cargar LLM asociado
    if only_active:
        stmt = stmt.filter(VAPModel.is_active == True)
    stmt = stmt.offset(skip).limit(limit).order_by(VAPModel.name)
    result = await db.execute(stmt)
    return result.scalars().all()

async def update_virtual_agent_profile(
    db: AsyncSession, 
    db_profile: VAPModel, 
    profile_in: VirtualAgentProfileUpdate
) -> VAPModel:
    update_data = profile_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_profile, field, value)
    await db.commit()
    await db.refresh(db_profile)
    return await get_virtual_agent_profile_by_id(db, db_profile.id) # Devolver con relaciones

async def delete_virtual_agent_profile(db: AsyncSession, profile_id: int) -> Optional[VAPModel]:
    db_profile = await get_virtual_agent_profile_by_id(db, profile_id, load_relations=False) # No necesitamos el LLM para borrar
    if db_profile:
        # Verificar si está siendo usado por ContextDefinitions o ApiClients antes de borrar?
        await db.delete(db_profile)
        await db.commit()
        return db_profile
    return None

async def get_fully_loaded_profile(db: AsyncSession, profile_id: int) -> Optional[VAPModel]:
    """
    Wrapper que asegura que un perfil se obtiene con todas sus relaciones cargadas.
    Llama a la función existente con los parámetros correctos.
    """
    return await get_virtual_agent_profile_by_id(db, profile_id=profile_id, load_relations=True)