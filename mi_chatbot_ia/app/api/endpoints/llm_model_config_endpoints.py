from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.session import get_crud_db_session
from app.schemas.schemas import LLMModelConfigCreate, LLMModelConfigUpdate, LLMModelConfigResponse
from app.crud import crud_llm_model_config
from app.models.app_user import AppUser
from app.security.role_auth import require_roles

router = APIRouter(prefix="/api/v1/admin/llm-models", tags=["Admin - LLM Models"])

ROLES_CAN_MANAGE_LLM_CONFIGS = ["SuperAdmin", "ContextEditor"]
ROLES_CAN_VIEW_LLM_CONFIGS = ["SuperAdmin", "ContextEditor", "ApiClientManager"]

@router.post("/", response_model=LLMModelConfigResponse, status_code=status.HTTP_201_CREATED, summary="Create New LLM Model Configuration")
async def create_new_llm_model_config(model_in: LLMModelConfigCreate, db: AsyncSession = Depends(get_crud_db_session), current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_LLM_CONFIGS))):
    existing_model = await crud_llm_model_config.get_llm_model_config_by_identifier(db, identifier=model_in.model_identifier)
    if existing_model:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Un LLM con el identificador '{model_in.model_identifier}' ya existe.")
    
    new_model_db = await crud_llm_model_config.create_llm_model_config(db=db, model_in=model_in)
    
    response = LLMModelConfigResponse.model_validate(new_model_db)
    response.has_api_key = bool(new_model_db.api_key_encrypted)
    return response

@router.get("/", response_model=List[LLMModelConfigResponse], summary="Read All LLM Model Configurations")
async def read_all_llm_model_configs(skip: int = 0, limit: int = 100, only_active: Optional[bool] = None, db: AsyncSession = Depends(get_crud_db_session), current_user: AppUser = Depends(require_roles(ROLES_CAN_VIEW_LLM_CONFIGS))):
    db_models = await crud_llm_model_config.get_llm_model_configs(db, skip=skip, limit=limit, only_active=only_active)
    
    response_list = []
    for model in db_models:
        item = LLMModelConfigResponse.model_validate(model)
        item.has_api_key = bool(model.api_key_encrypted)
        response_list.append(item)
    return response_list

@router.get("/{model_id}", response_model=LLMModelConfigResponse)
async def read_llm_model_config_by_id(model_id: int, db: AsyncSession = Depends(get_crud_db_session), current_user: AppUser = Depends(require_roles(ROLES_CAN_VIEW_LLM_CONFIGS))):
    db_model = await crud_llm_model_config.get_llm_model_config_by_id(db, model_id=model_id)
    if db_model is None:
        raise HTTPException(status_code=404, detail="Configuración de modelo LLM no encontrada.")
    response = LLMModelConfigResponse.model_validate(db_model)
    response.has_api_key = bool(db_model.api_key_encrypted)
    return response

@router.put("/{model_id}", response_model=LLMModelConfigResponse)
async def update_existing_llm_model_config(model_id: int, model_in: LLMModelConfigUpdate, db: AsyncSession = Depends(get_crud_db_session), current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_LLM_CONFIGS))):
    db_model = await crud_llm_model_config.get_llm_model_config_by_id(db, model_id=model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="Configuración a actualizar no encontrada.")
    updated_model_db = await crud_llm_model_config.update_llm_model_config(db=db, db_model=db_model, model_in=model_in)
    response = LLMModelConfigResponse.model_validate(updated_model_db)
    response.has_api_key = bool(updated_model_db.api_key_encrypted)
    return response

@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_model_configuration(model_id: int, db: AsyncSession = Depends(get_crud_db_session), current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_LLM_CONFIGS))):
    success = await crud_llm_model_config.delete_llm_model_config(db, model_id=model_id)
    if not success:
        raise HTTPException(status_code=404, detail="Configuración no encontrada para eliminar.")
    return None