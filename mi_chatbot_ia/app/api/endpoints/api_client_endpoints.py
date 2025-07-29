# app/api/endpoints/api_client_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.session import get_crud_db_session
from app.crud import crud_api_client
from app.schemas.schemas import (
    ApiClientCreate, 
    ApiClientUpdate, 
    ApiClientResponse,
    ApiClientWithPlainKeyResponse
)
from app.models.app_user import AppUser
from app.security.role_auth import require_roles

router = APIRouter(
     prefix="/api/v1/admin/api_clients",
     tags=["Admin - API Clients"] # Este tag será usado en OpenAPI
)

# Definición de roles para los endpoints (ya los tenías)
ROLES_MANAGE_API_CLIENTS = ["SuperAdmin"] 
ROLES_VIEW_API_CLIENTS = ["SuperAdmin", "ContextEditor", "ApiClientManager"]

MENU_API_CLIENTS = "Clientes API"

@router.post(
    "/", 
    response_model=ApiClientWithPlainKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New API Client",
    operation_id="create_new_api_client" # Operation ID explícito y más corto
)
async def create_new_api_client_endpoint(
    api_client_in: ApiClientCreate, # Body de la petición
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_API_CLIENTS)),
):
    """
    Crea un nuevo cliente API y genera una API Key única para él.
    La API Key generada (api_key_plain) será parte de la respuesta y DEBE ser copiada.
    El objeto `settings` debe adherirse a `ApiClientSettingsSchema`.
    """
    print(f"API_CLIENT_EP (Create): Admin '{current_user.username_ad}' creando cliente '{api_client_in.name}'.")
    existing_client = await crud_api_client.get_api_client_by_name(db, api_client_in.name)
    if existing_client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un cliente API con el nombre '{api_client_in.name}'."
        )
    
    db_api_client_obj = await crud_api_client.create_api_client(db, api_client_in)
    return db_api_client_obj


@router.get(
    "/", 
    response_model=List[ApiClientResponse], 
    summary="Read All API Clients",
    operation_id="read_all_api_clients" # Operation ID explícito
)
async def read_all_api_clients_endpoint(
    skip: int = Query(0, ge=0, description="Número de registros a saltar para paginación."),
    limit: int = Query(100, ge=1, le=100, description="Máximo número de registros a devolver."),
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_API_CLIENTS)) 
):
    """
    Obtiene una lista de clientes API (paginada).
    No se muestra `api_key_plain`. Se incluyen `allowed_contexts_details`.
    """
    print(f"API_CLIENT_EP (List): Admin '{current_user.username_ad}' listando clientes.")
    api_clients_list = await crud_api_client.get_api_clients(db, skip=skip, limit=limit)
    return api_clients_list


@router.get(
    "/{api_client_id}", 
    response_model=ApiClientResponse, 
    summary="Read API Client by ID",
    operation_id="read_api_client_by_id" # Operation ID explícito
)
async def read_api_client_by_id_endpoint(
    api_client_id: int, # Parámetro de ruta
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_API_CLIENTS))
):
    """
    Obtiene un cliente API por su ID.
    No se muestra `api_key_plain`. Se incluyen `allowed_contexts_details`.
    """
    print(f"API_CLIENT_EP (Get ID): Admin '{current_user.username_ad}' obteniendo cliente ID: {api_client_id}.")
    db_api_client = await crud_api_client.get_api_client_by_id(db, api_client_id)
    if db_api_client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente API no encontrado.")
    return db_api_client


@router.put(
    "/{api_client_id}", 
    response_model=ApiClientResponse, 
    summary="Update Existing API Client",
    operation_id="update_api_client_by_id" # Operation ID explícito
)
async def update_existing_api_client_endpoint(
    api_client_id: int, # Parámetro de ruta
    api_client_update_in: ApiClientUpdate, # Body de la petición
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_API_CLIENTS))
):
    """
    Actualiza un cliente API existente. No regenera la API Key.
    El objeto `settings` (si se envía) debe adherirse a `ApiClientSettingsSchema`.
    """
    print(f"API_CLIENT_EP (Update): Admin '{current_user.username_ad}' actualizando cliente ID: {api_client_id}.")
    db_api_client_to_update = await crud_api_client.get_api_client_by_id(db, api_client_id)
    if db_api_client_to_update is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente API a actualizar no encontrado.")
    
    if api_client_update_in.name and api_client_update_in.name != db_api_client_to_update.name:
        existing_client_with_new_name = await crud_api_client.get_api_client_by_name(db, api_client_update_in.name)
        if existing_client_with_new_name and existing_client_with_new_name.id != api_client_id:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Ya existe otro cliente API con el nombre '{api_client_update_in.name}'.")

    updated_client = await crud_api_client.update_api_client(db, db_api_client_to_update, api_client_update_in)
    return updated_client


@router.post(
    "/{api_client_id}/regenerate_key", 
    response_model=ApiClientWithPlainKeyResponse,
    summary="Regenerate API Key",
    operation_id="regenerate_api_key_for_client" # Operation ID explícito
)
async def regenerate_api_key_for_client_endpoint(
    api_client_id: int, # Parámetro de ruta
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_API_CLIENTS))
):
    """
    Genera una nueva API Key para un cliente existente y la devuelve (una vez).
    La clave antigua se invalida.
    """
    print(f"API_CLIENT_EP (Regen Key): Admin '{current_user.username_ad}' regenerando key para ID: {api_client_id}.")
    db_api_client_to_regen = await crud_api_client.get_api_client_by_id(db, api_client_id)
    if db_api_client_to_regen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente API no encontrado para regenerar key.")
    
    regenerated_client = await crud_api_client.regenerate_api_key(db, db_api_client_to_regen)
    return regenerated_client


@router.delete(
    "/{api_client_id}", 
    status_code=status.HTTP_204_NO_CONTENT, 
    summary="Delete API Client",
    operation_id="delete_api_client_by_id" # Operation ID explícito
)
async def delete_api_client_endpoint(
    api_client_id: int, # Parámetro de ruta
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_API_CLIENTS))
):
    """
    Elimina un cliente API.
    """
    print(f"API_CLIENT_EP (Delete): Admin '{current_user.username_ad}' eliminando cliente ID: {api_client_id}.")
    deleted_client = await crud_api_client.delete_api_client(db, api_client_id)
    if deleted_client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente API no encontrado para eliminar.")
    # No se devuelve nada en un 204
    return None