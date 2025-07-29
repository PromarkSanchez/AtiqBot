# app/api/endpoints/admin_app_users_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import traceback

from app.db.session import get_crud_db_session

# --- SCHEMAS ---
# Unificamos la importación de schemas que usaremos.
# Asegúrate de que las definiciones de estos schemas estén en su lugar correcto.
from app.schemas.schemas import (
    AppUserLocalCreate, 
    AppUserResponse, 
    AppUserUpdate
)

# --- CRUD y MODELOS ---
from app.crud import crud_app_user
from app.models.app_user import AppUser

# --- SEGURIDAD ---
from app.security.role_auth import require_roles 


# ==============================
# === Router y Constantes ===
# ==============================
router = APIRouter(
prefix="/api/v1/admin/app-user-management",
tags=["Admin - App User Management"],
)

MENU_GESTION_USUARIOS = "Usuarios Admin"


# ===============================================
# === ENDPOINT PARA CREAR USUARIOS (Create)   ===
# ===============================================
@router.post("/", response_model=AppUserResponse, status_code=status.HTTP_201_CREATED, summary="Create a new local Admin User")
async def create_local_admin_user_endpoint(
    user_in: AppUserLocalCreate,
    db: AsyncSession = Depends(get_crud_db_session),
    # Solo SuperAdmin puede crear otros administradores, usando tu sistema de seguridad.
    current_admin_creator: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_GESTION_USUARIOS))
):
    """
    Crea un nuevo usuario administrador de tipo 'local' con contraseña.
    - El username (DNI) y el email deben ser únicos.
    - Requiere rol de SuperAdmin.
    """
    print(f"APP_USERS_API (Create): Admin '{current_admin_creator.username_ad}' creando nuevo usuario local '{user_in.username_ad}'.")
    
    existing_user = await crud_app_user.get_app_user_by_username_ad(db, username_ad=user_in.username_ad)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"El DNI (username) '{user_in.username_ad}' ya está registrado.")

    if user_in.email:
        existing_email_user = await crud_app_user.get_app_user_by_email(db, email=user_in.email)
        if existing_email_user:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"El email '{user_in.email}' ya está en uso.")
            
    try:
        new_user = await crud_app_user.create_local_user(db, user_in=user_in)
        return new_user
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        print(f"APP_USERS_API: Error crítico creando usuario local: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error interno al crear el usuario.")


# =========================================
# === ENDPOINTS PARA LEER DATOS (Read)  ===
# =========================================
@router.get("/", response_model=List[AppUserResponse], summary="List all Admin Users")
async def read_all_app_users_endpoint(
    current_user: AppUser = Depends(require_roles(menu_name=MENU_GESTION_USUARIOS)),
    skip: int = 0,
    limit: int = 101,
    db: AsyncSession = Depends(get_crud_db_session)
):
    """Obtiene una lista de todos los usuarios administradores."""
    print(f"APP_USERS_API (List): Admin '{current_user.username_ad}' autorizado para ver usuarios.")
    users = await crud_app_user.get_all_app_users(db, skip=skip, limit=limit)
    return users


@router.get("/{app_user_id}", response_model=AppUserResponse, summary="Get Admin User by ID")
async def read_app_user_by_id_endpoint(
    app_user_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_GESTION_USUARIOS))
):
    """Obtiene los detalles de un usuario administrador específico."""
    print(f"APP_USERS_API (Get ID): Admin '{current_user.username_ad}' obteniendo AppUser ID: {app_user_id}.")
    
    is_superadmin = any(role.name == "SuperAdmin" for role in current_user.roles if role)
    if not is_superadmin and current_user.id != app_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para ver el perfil de otro usuario.")

    db_app_user = await crud_app_user.get_app_user_by_id(db, user_id=app_user_id)
    if db_app_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AppUser no encontrado.")
    return db_app_user


# ===============================================
# === ENDPOINT PARA ACTUALIZAR (Update)       ===
# ===============================================
@router.put("/{app_user_id}", response_model=AppUserResponse, summary="Update an Admin User")
async def update_app_user_endpoint(
    app_user_id: int,
    user_in: AppUserUpdate,  # Usamos el schema de actualización genérico
    db: AsyncSession = Depends(get_crud_db_session),
    current_admin_updater: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_GESTION_USUARIOS))
):
    """
    Actualiza los detalles de un usuario administrador (email, nombre, estado, roles).
    - Requiere rol de SuperAdmin.
    - Nota: Este endpoint no cambia la contraseña.
    """
    print(f"APP_USERS_API (Update): Admin '{current_admin_updater.username_ad}' actualizando AppUser ID: {app_user_id}")
    
    db_user_to_update = await crud_app_user.get_app_user_by_id(db, user_id=app_user_id)
    if not db_user_to_update:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AppUser a actualizar no encontrado.")
    
    if user_in.email and user_in.email != db_user_to_update.email:
        existing_email_user = await crud_app_user.get_app_user_by_email(db, email=user_in.email)
        if existing_email_user and existing_email_user.id != app_user_id:
            raise HTTPException(status_code=409, detail="El nuevo email ya está en uso por otro usuario.")
            
    try:
        updated_user = await crud_app_user.update_user(db=db, db_user=db_user_to_update, user_in=user_in)
        return updated_user
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        print(f"APP_USERS_API: Error crítico actualizando AppUser ID {app_user_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error interno al actualizar el AppUser.")


# ============================================
# === ENDPOINT DE ELIMINACIÓN (Delete)     ===
# ============================================
@router.delete("/{app_user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an Admin User")
async def delete_app_user_endpoint(
    app_user_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_admin_deleter: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_GESTION_USUARIOS))
):
    """
    Elimina PERMANENTEMENTE un usuario administrador del sistema.
    - Requiere rol de SuperAdmin.
    """
    print(f"APP_USERS_API (Delete): Admin '{current_admin_deleter.username_ad}' intentando eliminar AppUser ID: {app_user_id}")

    if current_admin_deleter.id == app_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes eliminar tu propia cuenta.")

    try:
        await crud_app_user.delete_user(db, user_id=app_user_id)
        # HTTP 204 No Content no debe devolver cuerpo. Se retorna None implícitamente.
    except ValueError: # Este error lo lanzamos desde el CRUD si no se encuentra el usuario
        raise HTTPException(status_code=404, detail=f"Usuario con ID {app_user_id} no encontrado.")
    except Exception as e:
        print(f"APP_USERS_API: Error crítico eliminando AppUser ID {app_user_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error interno al eliminar el AppUser.")
    