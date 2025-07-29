# app/api/v1/admin/app_users_api.py
from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession # type: ignore
from sqlalchemy.future import select as future_select # Necesario para el get_all # type: ignore
from sqlalchemy.orm import selectinload # type: ignore # Necesario para el get_all
from typing import List, Optional

from app.db.session import get_crud_db_session
from app.schemas.admin_auth import AppUserResponse, AppUserUpdateByAdmin
from app.crud import crud_app_user, crud_role # Necesitamos crud_role para la validación de SuperAdmin
from app.models.app_user import AppUser
# Quitar: from app.api.v1.admin.auth_api import get_current_active_admin_user
from app.security.role_auth import require_roles # <-- NUEVA IMPORTACIÓN
 
router = APIRouter(
   prefix="/api/v1/admin/app-user-management",
    tags=["Admin - App User Management"], # O el tag que decidiste
    # QUITAMOS LA DEPENDENCIA GLOBAL
    # dependencies=[Depends(get_current_active_admin_user)]
)

# Constantes de roles
SUPERADMIN_ROLE = ["SuperAdmin"]
# Puedes definir más conjuntos de roles si es necesario
ROLES_CAN_VIEW_USERS = ["SuperAdmin", "LogViewer"] # <-- AÑADIMOS LogViewer

@router.get("/", response_model=List[AppUserResponse])
async def read_all_app_users_endpoint(
    current_user: AppUser = Depends(require_roles(ROLES_CAN_VIEW_USERS)), # Solo SuperAdmin lista todos
    skip: int = 0,
    limit: int = 101,
    db: AsyncSession = Depends(get_crud_db_session)
):
    print(f"APP_USERS_API (List): Admin '{current_user.username_ad}' listando AppUsers.")
    # Asegúrate que `get_all_app_users` existe en `crud_app_user.py`
    if not hasattr(crud_app_user, "get_all_app_users"):
        raise NotImplementedError("crud_app_user.get_all_app_users no está implementado.")
    users = await crud_app_user.get_all_app_users(db, skip=skip, limit=limit)
    return users


@router.get("/{app_user_id}", response_model=AppUserResponse)
async def read_app_user_by_id_endpoint(
    app_user_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    # Un SuperAdmin puede ver cualquier usuario.
    # Un usuario también podría ver su propio perfil (lógica adicional aquí).
    current_user: AppUser = Depends(require_roles(ROLES_CAN_VIEW_USERS)) # Por ahora, simplificado
):
    print(f"APP_USERS_API (Get ID): Admin '{current_user.username_ad}' obteniendo AppUser ID: {app_user_id}.")
    
    # Permitir a un usuario ver su propio perfil, o a un SuperAdmin ver cualquiera
    can_view = False
    if current_user.id == app_user_id: # Puede ver su propio perfil
        can_view = True
    else: # Verificamos si es SuperAdmin para ver a otros
        user_is_superadmin = any(role.name == "SuperAdmin" for role in current_user.roles if role)
        if user_is_superadmin:
            can_view = True
    
    if not can_view:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para ver este perfil de usuario.")

    db_app_user = await crud_app_user.get_app_user_by_id(db, user_id=app_user_id)
    if db_app_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AppUser no encontrado.")
    return db_app_user


@router.put("/{app_user_id}", response_model=AppUserResponse)
async def update_app_user_by_admin_id_endpoint(
    app_user_id: int,
    user_in_update: AppUserUpdateByAdmin,
    db: AsyncSession = Depends(get_crud_db_session),
    current_admin_updater: AppUser = Depends(require_roles(ROLES_CAN_VIEW_USERS)) # Solo SuperAdmin actualiza
):
    print(f"APP_USERS_API (Update): Admin '{current_admin_updater.username_ad}' "
          f"actualizando AppUser ID: {app_user_id}")
    
    db_user_to_be_updated = await crud_app_user.get_app_user_by_id(db, user_id=app_user_id)
    if not db_user_to_be_updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AppUser a actualizar no encontrado.")

    # Lógica para prevenir que un SuperAdmin se quite a sí mismo el rol de SuperAdmin si es el último
    # o si se está intentando modificar el rol SuperAdmin de forma no permitida.
    is_updating_self = (current_admin_updater.id == db_user_to_be_updated.id)
    
    if is_updating_self and user_in_update.role_ids is not None: # Si el superadmin se actualiza a sí mismo los roles
        is_currently_superadmin = any(role.name == "SuperAdmin" for role in current_admin_updater.roles if role)
        if is_currently_superadmin:
            # Buscar el ID del rol "SuperAdmin"
            superadmin_role_db_obj = await crud_role.get_role_by_name(db, "SuperAdmin")
            if superadmin_role_db_obj and superadmin_role_db_obj.id not in user_in_update.role_ids:
                # Se está intentando quitar el rol SuperAdmin
                # Aquí se podría añadir lógica para contar cuántos otros SuperAdmins existen
                # y prevenir si este es el último. Por ahora, se lo permitimos con advertencia.
                print(f"ADVERTENCIA APP_USERS_API: SuperAdmin '{current_admin_updater.username_ad}' está intentando quitarse su propio rol SuperAdmin.")
                # Podrías lanzar una HTTPException aquí si no quieres permitirlo.
                # raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Un SuperAdmin no puede quitarse su propio rol de SuperAdmin.")

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
        traceback.print_exc() # type: ignore
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al actualizar el AppUser.")

@router.delete("/{app_user_id}", 
                # response_model=AppUserResponse, # Opcional: si devuelves el usuario
                status_code=status.HTTP_204_NO_CONTENT, # Común para DELETE exitoso sin contenido de respuesta
                summary="Delete App User By Admin")
async def delete_app_user_by_admin_endpoint(
    app_user_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_admin_deleter: AppUser = Depends(require_roles(ROLES_CAN_VIEW_USERS)) # Solo SuperAdmin elimina
):
    print(f"APP_USERS_API (Delete): Admin '{current_admin_deleter.username_ad}' "
          f"intentando eliminar AppUser ID: {app_user_id}")

    db_user_to_delete = await crud_app_user.get_app_user_by_id(db, user_id=app_user_id)
    if not db_user_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AppUser a eliminar no encontrado.")

    # Lógica de seguridad: ¿Se puede eliminar a este usuario?
    # Por ejemplo, no permitir que un SuperAdmin se elimine a sí mismo si es el único.
    if current_admin_deleter.id == db_user_to_delete.id:
        # Podrías añadir lógica para contar cuántos SuperAdmins quedan
        is_superadmin = any(role.name == "SuperAdmin" for role in db_user_to_delete.roles if role)
        if is_superadmin:
            # Lógica para prevenir la eliminación del último SuperAdmin (ej. consultar total de SuperAdmins)
            # total_superadmins = await crud_app_user.count_superadmins(db)
            # if total_superadmins <= 1:
            #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se puede eliminar al único SuperAdmin.")
            print(f"ADVERTENCIA APP_USERS_API: SuperAdmin '{current_admin_deleter.username_ad}' está intentando eliminarse a sí mismo.")
            # Decide si lo permites o no.

    try:
        # Opción 1: Eliminación Lógica (ej. marcar como inactivo permanentemente)
        # Esto requeriría una función en crud_app_user, por ejemplo:
        # await crud_app_user.mark_app_user_as_deleted(db=db, user_id=app_user_id)
        # O simplemente actualizarlo a un estado inactivo y sin roles:
        delete_payload = AppUserUpdateByAdmin(is_active_local=False, role_ids=[]) # Quitar roles también
        await crud_app_user.update_app_user_details_by_admin(db, db_user_to_update=db_user_to_delete, user_update_data=delete_payload)
        print(f"APP_USERS_API: AppUser ID {app_user_id} marcado como inactivo (eliminación lógica).")

        # Opción 2: Eliminación Física (Directamente desde la BD)
        # await crud_app_user.delete_app_user(db=db, user_id=app_user_id) # Necesitarías esta función en crud
        # print(f"APP_USERS_API: AppUser ID {app_user_id} eliminado físicamente.")
        
        # Devuelve nada (204 No Content) o el objeto eliminado (si usas response_model=AppUserResponse)
        return None # Para 204 No Content
        # return db_user_to_delete # Si devuelves el usuario

    except ValueError as ve: # Por si el CRUD lanza errores específicos
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e_delete_user:
        print(f"APP_USERS_API: Error crítico eliminando AppUser ID {app_user_id}: {e_delete_user}")
        # import traceback # Asegúrate de tener esta importación si no está global
        # traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al eliminar el AppUser.")