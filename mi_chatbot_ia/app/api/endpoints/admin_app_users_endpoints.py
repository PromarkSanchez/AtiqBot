# app/api/endpoints/admin_app_users_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import traceback

from app.db.session import get_crud_db_session
from app.schemas.schemas import AppUserLocalCreate, AppUserResponse, AppUserUpdate
from app.crud import crud_app_user
from app.models.app_user import AppUser
from app.security.role_auth import require_roles 

router = APIRouter(
    prefix="/api/v1/admin/app-user-management",
    tags=["Admin - App User Management"],
)

MENU_GESTION_USUARIOS = "Usuarios Admin"

@router.post("/", response_model=AppUserResponse, status_code=status.HTTP_201_CREATED)
async def create_local_admin_user_endpoint(
    user_in: AppUserLocalCreate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_admin_creator: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_GESTION_USUARIOS))
):
    existing_user = await crud_app_user.get_app_user_by_username_ad(db, username_ad=user_in.username_ad)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"El DNI (username) '{user_in.username_ad}' ya está registrado.")

    if user_in.email:
        existing_email_user = await crud_app_user.get_app_user_by_email(db, email=user_in.email)
        if existing_email_user:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"El email '{user_in.email}' ya está en uso.")
            
    new_user = await crud_app_user.create_local_user(db, user_in=user_in)
    return new_user

@router.get("/", response_model=List[AppUserResponse])
async def read_all_app_users_endpoint(
    current_user: AppUser = Depends(require_roles(menu_name=MENU_GESTION_USUARIOS)),
    skip: int = 0,
    limit: int = 101,
    db: AsyncSession = Depends(get_crud_db_session)
):
    users = await crud_app_user.get_all_app_users(db, skip=skip, limit=limit)
    return users

@router.get("/{app_user_id}", response_model=AppUserResponse)
async def read_app_user_by_id_endpoint(
    app_user_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_GESTION_USUARIOS))
):
    is_superadmin = any(role.name == "SuperAdmin" for role in current_user.roles if role)
    if not is_superadmin and current_user.id != app_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para ver el perfil de otro usuario.")

    db_app_user = await crud_app_user.get_app_user_by_id(db, user_id=app_user_id)
    if db_app_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AppUser no encontrado.")
    return db_app_user

@router.put("/{app_user_id}", response_model=AppUserResponse)
async def update_app_user_endpoint(
    app_user_id: int,
    user_in: AppUserUpdate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_admin_updater: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_GESTION_USUARIOS))
):
    print(f"APP_USERS_API (Update): Admin '{current_admin_updater.username_ad}' actualizando AppUser ID: {app_user_id}")
    print(f"DEBUG: Datos recibidos del frontend: {user_in.model_dump(exclude_unset=True)}")

    db_user_to_update = await crud_app_user.get_app_user_by_id(db, user_id=app_user_id)
    if not db_user_to_update:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario a actualizar no encontrado.")
    
    if user_in.email and user_in.email != db_user_to_update.email:
        existing_email_user = await crud_app_user.get_app_user_by_email(db, email=user_in.email)
        if existing_email_user and existing_email_user.id != app_user_id:
            raise HTTPException(status_code=409, detail="El nuevo email ya está en uso por otro usuario.")
            
    updated_user = await crud_app_user.update_user(db=db, db_user=db_user_to_update, user_in=user_in)
    return updated_user

@router.delete("/{app_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_app_user_endpoint(
    app_user_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_admin_deleter: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_GESTION_USUARIOS))
):
    if current_admin_deleter.id == app_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes eliminar tu propia cuenta.")

    deleted = await crud_app_user.delete_user(db, user_id=app_user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Usuario con ID {app_user_id} no encontrado.")