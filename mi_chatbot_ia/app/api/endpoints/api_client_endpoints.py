# Archivo: mi_chatbot_ia/app/api/endpoints/api_client_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_crud_db_session
from app.crud import crud_api_client
from app.schemas.schemas import (
    ApiClientCreate, 
    ApiClientUpdate, 
    ApiClientResponse,
    ApiClientWithPlainKeyResponse,
    WebchatUIConfig
)
from app.models.app_user import AppUser
from app.security.role_auth import require_roles

# =======================================================
# === ROUTER #1: PARA EL PANEL DE ADMINISTRACIÓN (PRIVADO) ===
# =======================================================
router = APIRouter(
     prefix="/api/v1/admin/api_clients",
     tags=["Admin - API Clients"]
)

MENU_API_CLIENTS = "Clientes API" 

@router.post("/", response_model=ApiClientWithPlainKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_new_api_client_endpoint(api_client_in: ApiClientCreate, db: AsyncSession = Depends(get_crud_db_session), current_user: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_API_CLIENTS))):
    existing_client = await crud_api_client.get_api_client_by_name(db, api_client_in.name)
    if existing_client:
        raise HTTPException(status_code=400, detail=f"Ya existe un cliente API con el nombre '{api_client_in.name}'.")
    return await crud_api_client.create_api_client(db, api_client_in)

@router.get("/", response_model=List[ApiClientResponse])
async def read_all_api_clients_endpoint(skip: int = Query(0), limit: int = Query(100), db: AsyncSession = Depends(get_crud_db_session), current_user: AppUser = Depends(require_roles(menu_name=MENU_API_CLIENTS))):
    return await crud_api_client.get_api_clients(db, skip=skip, limit=limit)

@router.get("/{api_client_id}", response_model=ApiClientResponse)
async def read_api_client_by_id_endpoint(api_client_id: int, db: AsyncSession = Depends(get_crud_db_session), current_user: AppUser = Depends(require_roles(menu_name=MENU_API_CLIENTS))):
    db_api_client = await crud_api_client.get_api_client_by_id(db, api_client_id)
    if db_api_client is None:
        raise HTTPException(status_code=404, detail="Cliente API no encontrado.")
    return db_api_client

@router.put("/{api_client_id}", response_model=ApiClientResponse)
async def update_existing_api_client_endpoint(api_client_id: int, api_client_update_in: ApiClientUpdate, db: AsyncSession = Depends(get_crud_db_session), current_user: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_API_CLIENTS))):
    db_api_client_to_update = await crud_api_client.get_api_client_by_id(db, api_client_id)
    if not db_api_client_to_update:
        raise HTTPException(status_code=404, detail="Cliente API a actualizar no encontrado.")
    return await crud_api_client.update_api_client(db, db_api_client_to_update, api_client_update_in)

@router.post("/{api_client_id}/regenerate_key", response_model=ApiClientWithPlainKeyResponse)
async def regenerate_api_key_for_client_endpoint(api_client_id: int, db: AsyncSession = Depends(get_crud_db_session), current_user: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_API_CLIENTS))):
    db_api_client_to_regen = await crud_api_client.get_api_client_by_id(db, api_client_id)
    if not db_api_client_to_regen:
        raise HTTPException(status_code=404, detail="Cliente API no encontrado para regenerar key.")
    return await crud_api_client.regenerate_api_key(db, db_api_client_to_regen)

@router.delete("/{api_client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_client_endpoint(api_client_id: int, db: AsyncSession = Depends(get_crud_db_session), current_user: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_API_CLIENTS))):
    deleted_client = await crud_api_client.delete_api_client(db, api_client_id)
    if not deleted_client:
        raise HTTPException(status_code=404, detail="Cliente API no encontrado para eliminar.")
    return None

@router.put("/{api_client_id}/webchat-ui-config", response_model=ApiClientResponse)
async def update_webchat_ui_config_endpoint(api_client_id: int, config_in: WebchatUIConfig, db: AsyncSession = Depends(get_crud_db_session), current_user: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_API_CLIENTS))):
    updated_client = await crud_api_client.update_api_client_webchat_config(db, api_client_id=api_client_id, config_in=config_in)
    if not updated_client:
        raise HTTPException(status_code=404, detail="Cliente API no encontrado.")
    return updated_client

# ===============================================
# === ROUTER #2: PARA EL WIDGET (PÚBLICO)     ===
# ===============================================
public_router = APIRouter(
    prefix="/api/v1/public",
    tags=["Public - Webchat"]
)

@public_router.get(
    "/webchat-config",
    response_model=WebchatUIConfig,
    summary="Get Public Webchat UI Configuration"
)
async def get_public_webchat_config(
    x_api_key: str = Header(...),
    db: AsyncSession = Depends(get_crud_db_session)
):
    hashed_key = crud_api_client.hash_api_key(x_api_key)
    
    # --- ¡CORRECCIÓN APLICADA AQUÍ! ---
    # La función CRUD espera `hashed_api_key`, así que se lo pasamos con ese nombre.
    api_client = await crud_api_client.get_api_client_by_hashed_key(db, hashed_api_key=hashed_key)
    
    if not api_client or not api_client.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key not found or client is inactive.")

    if not api_client.webchat_ui_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webchat UI configuration not set for this client.")
        
    if not isinstance(api_client.webchat_ui_config, dict):
         raise HTTPException(status_code=500, detail="Webchat UI configuration is malformed.")
        
    return api_client.webchat_ui_config