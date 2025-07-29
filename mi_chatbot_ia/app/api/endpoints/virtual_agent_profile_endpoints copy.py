# app/api/endpoints/virtual_agent_profile_endpoints.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.session import get_crud_db_session
from app.schemas.schemas import VirtualAgentProfileCreate, VirtualAgentProfileUpdate, VirtualAgentProfileResponse
from app.crud import crud_virtual_agent_profile, crud_llm_model_config # Para validar FK
from app.models.app_user import AppUser
from app.security.role_auth import require_roles

router = APIRouter()

ROLES_CAN_MANAGE_VAPS = ["SuperAdmin", "ContextEditor"] 
ROLES_CAN_VIEW_VAPS = ["SuperAdmin", "ContextEditor", "ApiClientManager"]

@router.post(
    "/virtual-agent-profiles", 
    response_model=VirtualAgentProfileResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create New Virtual Agent Profile",
    tags=["Admin - Virtual Agent Profiles"]
)
async def create_new_virtual_agent_profile(
    profile_in: VirtualAgentProfileCreate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_VAPS)),
):
    existing_profile = await crud_virtual_agent_profile.get_virtual_agent_profile_by_name(db, name=profile_in.name)
    if existing_profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Perfil de Agente Virtual '{profile_in.name}' ya existe.")
    
    # Validar que el llm_model_config_id existe
    llm_config = await crud_llm_model_config.get_llm_model_config_by_id(db, profile_in.llm_model_config_id)
    if not llm_config:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"LLMModelConfig con ID {profile_in.llm_model_config_id} no encontrado.")
    if not llm_config.is_active:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"LLMModelConfig ID {profile_in.llm_model_config_id} está inactivo.")

    return await crud_virtual_agent_profile.create_virtual_agent_profile(db=db, profile_in=profile_in)

@router.get(
    "/virtual-agent-profiles", 
    response_model=List[VirtualAgentProfileResponse],
    summary="Read All Virtual Agent Profiles",
    tags=["Admin - Virtual Agent Profiles"]
)
async def read_all_virtual_agent_profiles(
    skip: int = 0,
    limit: int = 100,
    only_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_VIEW_VAPS)),
):
    if only_active is not None:
        return await crud_virtual_agent_profile.get_virtual_agent_profiles(db, skip=skip, limit=limit, only_active=only_active)
    return await crud_virtual_agent_profile.get_virtual_agent_profiles(db, skip=skip, limit=limit)

@router.get(
    "/virtual-agent-profiles/{profile_id}", 
    response_model=VirtualAgentProfileResponse,
    summary="Read Virtual Agent Profile by ID",
    tags=["Admin - Virtual Agent Profiles"]
)
async def read_virtual_agent_profile_by_id(
    profile_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_VIEW_VAPS)),
):
    db_profile = await crud_virtual_agent_profile.get_virtual_agent_profile_by_id(db, profile_id=profile_id)
    if db_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil de Agente Virtual no encontrado.")
    return db_profile

@router.put(
    "/virtual-agent-profiles/{profile_id}", 
    response_model=VirtualAgentProfileResponse,
    summary="Update Existing Virtual Agent Profile",
    tags=["Admin - Virtual Agent Profiles"]
)
async def update_existing_virtual_agent_profile(
    profile_id: int,
    profile_in: VirtualAgentProfileUpdate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_VAPS)),
):
    db_profile = await crud_virtual_agent_profile.get_virtual_agent_profile_by_id(db, profile_id=profile_id)
    if db_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil de Agente Virtual a actualizar no encontrado.")

    if profile_in.name and profile_in.name != db_profile.name:
        existing_name = await crud_virtual_agent_profile.get_virtual_agent_profile_by_name(db, name=profile_in.name)
        if existing_name and existing_name.id != profile_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Otro Perfil de Agente Virtual ya usa el nombre '{profile_in.name}'.")
    
    if profile_in.llm_model_config_id:
        llm_config = await crud_llm_model_config.get_llm_model_config_by_id(db, profile_in.llm_model_config_id)
        if not llm_config:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"LLMModelConfig con ID {profile_in.llm_model_config_id} no encontrado para la actualización.")
        if not llm_config.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"LLMModelConfig ID {profile_in.llm_model_config_id} está inactivo.")

    return await crud_virtual_agent_profile.update_virtual_agent_profile(db=db, db_profile=db_profile, profile_in=profile_in)

@router.delete(
    "/virtual-agent-profiles/{profile_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Virtual Agent Profile",
    tags=["Admin - Virtual Agent Profiles"]
)
async def delete_virtual_agent_profile_entry( # Nombre completo
    profile_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_VAPS)),
):
    deleted_profile = await crud_virtual_agent_profile.delete_virtual_agent_profile(db, profile_id=profile_id)
    if deleted_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil de Agente Virtual no encontrado para eliminar.")
    return None