# app/api/endpoints/virtual_agent_profile_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.services import prompt_generator_service

from app.db.session import get_crud_db_session
from app.schemas.schemas import (
    VirtualAgentProfileCreate, 
    VirtualAgentProfileUpdate, 
    VirtualAgentProfileResponse,
    GeneratePromptRequest, 
    GeneratedPromptSetResponse
)
from app.crud import crud_virtual_agent_profile, crud_llm_model_config
from app.models.app_user import AppUser
from app.security.role_auth import require_roles

# Definimos el prefijo para todo el router.
router = APIRouter(
    prefix="/api/v1/admin/virtual-agent-profiles",
    tags=["Admin - Virtual Agent Profiles"]
)

 
ROLES_CAN_MANAGE_VAPS = ["SuperAdmin", "ContextEditor"] 
ROLES_CAN_VIEW_VAPS = ["SuperAdmin", "ContextEditor", "ApiClientManager"]


# --- ENDPOINTS CRUD ---
@router.post("/",  response_model=VirtualAgentProfileResponse, status_code=status.HTTP_201_CREATED, summary="Create New Virtual Agent Profile")
async def create_new_virtual_agent_profile(
    profile_in: VirtualAgentProfileCreate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_VAPS)),
):
    existing_profile = await crud_virtual_agent_profile.get_virtual_agent_profile_by_name(db, name=profile_in.name)
    if existing_profile:
        raise HTTPException(status_code=400, detail=f"Perfil de Agente Virtual '{profile_in.name}' ya existe.")
    
    llm_config = await crud_llm_model_config.get_llm_model_config_by_id(db, profile_in.llm_model_config_id)
    if not llm_config or not llm_config.is_active:
         raise HTTPException(status_code=400, detail=f"LLMModelConfig ID {profile_in.llm_model_config_id} es inválido o está inactivo.")

    return await crud_virtual_agent_profile.create_virtual_agent_profile(db=db, profile_in=profile_in)


@router.get("/", response_model=List[VirtualAgentProfileResponse], summary="Read All Virtual Agent Profiles")
async def read_all_virtual_agent_profiles(
    skip: int = 0, limit: int = 100, only_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_VIEW_VAPS)),
):
    # En el futuro, es posible que queramos cargar relaciones aquí también.
    return await crud_virtual_agent_profile.get_virtual_agent_profiles(db, skip=skip, limit=limit, only_active=only_active)


@router.get("/{profile_id}", response_model=VirtualAgentProfileResponse, summary="Read Virtual Agent Profile by ID")
async def read_virtual_agent_profile_by_id(
    profile_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_VIEW_VAPS)),
):
    # Asegurarse de que el CRUD carga las relaciones necesarias para el Response Model
    db_profile = await crud_virtual_agent_profile.get_virtual_agent_profile_by_id(db, profile_id=profile_id, load_relations=True)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Perfil de Agente Virtual no encontrado.")
    return db_profile


@router.put("/{profile_id}", response_model=VirtualAgentProfileResponse, summary="Update Existing Virtual Agent Profile")
async def update_existing_virtual_agent_profile(
    profile_id: int,
    profile_in: VirtualAgentProfileUpdate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_VAPS)),
):
    db_profile = await crud_virtual_agent_profile.get_virtual_agent_profile_by_id(db, profile_id=profile_id)
    if not db_profile:
        raise HTTPException(status_code=404, detail="Perfil de Agente Virtual no encontrado para actualizar.")
    
    # Aquí puedes añadir la lógica de validación para el nombre, llm_model_config_id, etc.
    
    return await crud_virtual_agent_profile.update_virtual_agent_profile(db=db, db_profile=db_profile, profile_in=profile_in)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Virtual Agent Profile")
async def delete_virtual_agent_profile_entry( 
    profile_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_VAPS)),
):
    deleted_profile = await crud_virtual_agent_profile.delete_virtual_agent_profile(db, profile_id=profile_id)
    if not deleted_profile:
        raise HTTPException(status_code=404, detail="Perfil de Agente Virtual no encontrado para eliminar.")
    return None

# --- ENDPOINT DEL ASISTENTE IA ---

@router.post(
    "/generate-prompt",
    response_model=GeneratedPromptSetResponse, # <-- Usamos el nuevo schema que espera 3 prompts
    status_code=status.HTTP_200_OK,
    summary="[IA] Genera un Conjunto de Prompts para un Agente"
)
async def generate_optimized_prompt_endpoint(
    request_data: GeneratePromptRequest,
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_VAPS)), 
    db: AsyncSession = Depends(get_crud_db_session),
):
    """
    Este endpoint genera el CONJUNTO COMPLETO de prompts (saludo, confirmación, y sistema)
    para un Agente Virtual, utilizando un LLM maestro.
    """
    try:
        # La llamada al servicio ahora devuelve un diccionario con los 3 prompts.
        prompt_dict = await prompt_generator_service.generate_optimized_prompt(
            db=db,
            request=request_data
        )
        
        # Simplemente devolvemos el diccionario. FastAPI y Pydantic se encargan del resto.
        return prompt_dict
    
    except HTTPException as e:
        # Re-lanza las excepciones controladas desde el servicio (ej. 404, 500).
        raise e
    except Exception as e:
        # Para cualquier otro error no esperado.
        print(f"ERROR INESPERADO en generate_optimized_prompt_endpoint: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Error al comunicarse con el servicio de LLM maestro."
        )