# app/api/endpoints/admin_app_users_endpoints.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import traceback  # Añadido para que el print_exc no dé error de importación

from app.db.session import get_crud_db_session
from app.schemas.admin_auth import AppUserResponse, AppUserUpdateByAdmin
from app.crud import crud_app_user, crud_role
from app.models.app_user import AppUser

# --- CAMBIO CLAVE: Importamos la nueva dependencia de permisos ---
from app.security.role_auth import require_roles 

router = APIRouter(
   prefix="/api/v1/admin/app-user-management",
    tags=["Admin - App User Management"],
)

# --- Constantes para los nombres de los menús (Fuente única de verdad) ---
# Esto hace el código más legible y fácil de mantener.
# Asegúrate de que coincida con el campo 'name' en tu tabla `admin_panel_menus`.
MENU_GESTION_USUARIOS = "Usuarios Admin"


@router.get("/", response_model=List[AppUserResponse])
async def read_all_app_users_endpoint(
    # --- CAMBIO: Ahora la protección se basa en el permiso del menú, no en un rol fijo ---
    current_user: AppUser = Depends(require_roles(menu_name=MENU_GESTION_USUARIOS)),
    skip: int = 0,
    limit: int = 101,
    db: AsyncSession = Depends(get_crud_db_session)
):
    print(f"APP_USERS_API (List): Admin '{current_user.username_ad}' autorizado para ver usuarios.")
    if not hasattr(crud_app_user, "get_all_app_users"):
        raise NotImplementedError("crud_app_user.get_all_app_users no está implementado.")
    users = await crud_app_user.get_all_app_users(db, skip=skip, limit=limit)
    return users


@router.get("/{app_user_id}", response_model=AppUserResponse)
async def read_app_user_by_id_endpoint(
    app_user_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    # --- CAMBIO: La protección de acceso a la API se basa en el permiso del menú ---
    current_user: AppUser = Depends(require_roles(menu_name=MENU_GESTION_USUARIOS))
):
    print(f"APP_USERS_API (Get ID): Admin '{current_user.username_ad}' obteniendo AppUser ID: {app_user_id}.")
    
    # La lógica de autorización fina (ver tu propio perfil vs ver otros) se mantiene.
    is_superadmin = any(role.name == "SuperAdmin" for role in current_user.roles if role)
    if not is_superadmin and current_user.id != app_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para ver el perfil de otro usuario.")

    db_app_user = await crud_app_user.get_app_user_by_id(db, user_id=app_user_id)
    if db_app_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AppUser no encontrado.")
    return db_app_user


@router.put("/{app_user_id}", response_model=AppUserResponse)
async def update_app_user_by_admin_id_endpoint(
    app_user_id: int,
    user_in_update: AppUserUpdateByAdmin,
    db: AsyncSession = Depends(get_crud_db_session),
    # --- CAMBIO: Aquí usamos una doble protección. Debe tener acceso al menú Y ser SuperAdmin. ---
    current_admin_updater: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_GESTION_USUARIOS))
):
    print(f"APP_USERS_API (Update): Admin '{current_admin_updater.username_ad}' actualizando AppUser ID: {app_user_id}")
    
    db_user_to_be_updated = await crud_app_user.get_app_user_by_id(db, user_id=app_user_id)
    if not db_user_to_be_updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AppUser a actualizar no encontrado.")

    # (El resto de tu lógica de actualización se mantiene igual)
    # ...
    try:
        updated_app_user = await crud_app_user.update_app_user_details_by_admin(
            db=db, 
            db_user_to_update=db_user_to_be_updated, 
            user_update_data=user_in_update
        )
        return updated_app_user
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e_update_user_exc:
        print(f"APP_USERS_API: Error crítico actualizando AppUser ID {app_user_id}: {e_update_user_exc}")
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al actualizar el AppUser.")


@router.delete("/{app_user_id}", 
                status_code=status.HTTP_204_NO_CONTENT,
                summary="Delete App User By Admin")
async def delete_app_user_by_admin_endpoint(
    app_user_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    # --- CAMBIO: También aplicamos la doble protección aquí. ---
    current_admin_deleter: AppUser = Depends(require_roles(roles=["SuperAdmin"], menu_name=MENU_GESTION_USUARIOS))
):
    print(f"APP_USERS_API (Delete): Admin '{current_admin_deleter.username_ad}' intentando eliminar AppUser ID: {app_user_id}")

    db_user_to_delete = await crud_app_user.get_app_user_by_id(db, user_id=app_user_id)
    if not db_user_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AppUser a eliminar no encontrado.")

    # (El resto de tu lógica de borrado se mantiene igual)
    # ...
    try:
        delete_payload = AppUserUpdateByAdmin(is_active_local=False, role_ids=[])
        await crud_app_user.update_app_user_details_by_admin(db, db_user_to_update=db_user_to_delete, user_update_data=delete_payload)
        print(f"APP_USERS_API: AppUser ID {app_user_id} marcado como inactivo (eliminación lógica).")
        return None

    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e_delete_user:
        print(f"APP_USERS_API: Error crítico eliminando AppUser ID {app_user_id}: {e_delete_user}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al eliminar el AppUser.")