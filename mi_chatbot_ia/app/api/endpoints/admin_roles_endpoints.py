# app/api/v1/admin/roles_api.py
from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession # type: ignore
from typing import List

from app.db.session import get_crud_db_session
from app.schemas.admin_auth import RoleCreate, RoleUpdate, RoleResponse
from app.crud import crud_role
from app.models.app_user import AppUser 
# Importar la dependencia de roles
from app.security.role_auth import require_roles 

router = APIRouter(
    prefix="/api/v1/admin/roles",
    tags=["Admin - Roles Management"],
    # Quitamos la dependencia global get_current_active_admin_user del router
    # porque require_roles ya la invoca y maneja la autenticación base.
)

# Definimos constantes para los roles para fácil reutilización y claridad
# Eventualmente, estos podrían venir de un enum o una configuración si se vuelven muy complejos
ROLE_SUPERADMIN = ["SuperAdmin"]
ROLE_ANY_AUTHENTICATED_ADMIN = [] # OJO: Usar con cuidado o no usar si se requiere rol específico.
                               # Por ahora, lo usamos para los GET que podrían ser más permisivos.
                               # En RoleChecker, si allowed_roles está vacío, por ahora, lo permitía.
                               # Es mejor ser explícito, ej. ROLES_VIEWER = ["SuperAdmin", "ContextEditor", "LogViewer"]
ROLES_CAN_VIEW = ["SuperAdmin", "ContextEditor", "LogViewer"] # Quiénes pueden ver roles

@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_new_role_endpoint(
    role_in: RoleCreate,
    db: AsyncSession = Depends(get_crud_db_session),
    # Solo usuarios con el rol "SuperAdmin" pueden crear nuevos roles
    current_user_with_permission: AppUser = Depends(require_roles(ROLE_SUPERADMIN)) 
):
    print(f"ROLES_API (Create): Admin '{current_user_with_permission.username_ad}' creando rol '{role_in.name}'.")
    existing_role = await crud_role.get_role_by_name(db, name=role_in.name)
    if existing_role:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Rol '{role_in.name}' ya existe.")
    return await crud_role.create_role(db=db, role_in=role_in)

@router.get("/", response_model=List[RoleResponse])
async def read_all_roles_endpoint(
    # Usuarios con cualquiera de estos roles pueden listar todos los roles
    current_user_with_permission: AppUser = Depends(require_roles(ROLES_CAN_VIEW)), 
    skip: int = 0,
    limit: int = 101,
    db: AsyncSession = Depends(get_crud_db_session)
):
    print(f"ROLES_API (List): Admin '{current_user_with_permission.username_ad}' listando roles.")
    return await crud_role.get_roles(db, skip=skip, limit=limit)

@router.get("/{role_id}", response_model=RoleResponse)
async def read_role_by_id_endpoint(
    role_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user_with_permission: AppUser = Depends(require_roles(ROLES_CAN_VIEW)) 
):
    print(f"ROLES_API (Get ID): Admin '{current_user_with_permission.username_ad}' obteniendo rol ID: {role_id}.")
    db_role = await crud_role.get_role_by_id(db, role_id=role_id)
    if db_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado.")
    return db_role

@router.put("/{role_id}", response_model=RoleResponse)
async def update_existing_role_endpoint(
    role_id: int,
    role_in: RoleUpdate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user_with_permission: AppUser = Depends(require_roles(ROLE_SUPERADMIN)) 
):
    print(f"ROLES_API (Update): Admin '{current_user_with_permission.username_ad}' actualizando rol ID: {role_id}.")
    db_role_to_update = await crud_role.get_role_by_id(db, role_id=role_id)
    if db_role_to_update is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado para actualizar.")
    
    if role_in.name and role_in.name != db_role_to_update.name:
        existing_role_with_new_name = await crud_role.get_role_by_name(db, name=role_in.name)
        if existing_role_with_new_name and existing_role_with_new_name.id != role_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Ya existe otro rol con el nombre '{role_in.name}'.")
            
    return await crud_role.update_role(db=db, db_role=db_role_to_update, role_in=role_in)

@router.delete("/{role_id}", response_model=RoleResponse)
async def delete_existing_role_endpoint(
    role_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user_with_permission: AppUser = Depends(require_roles(ROLE_SUPERADMIN))
):
    print(f"ROLES_API (Delete): Admin '{current_user_with_permission.username_ad}' eliminando rol ID: {role_id}.")
    
    target_role_to_delete = await crud_role.get_role_by_id(db, role_id=role_id)
    if target_role_to_delete is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado para eliminar.")
    # Protección para no borrar roles críticos por nombre
    if target_role_to_delete.name in ["SuperAdmin"]: # Lista de roles no borrables
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"El rol '{target_role_to_delete.name}' no puede ser eliminado.")
            
    # Considerar verificar si el rol está en uso por algún AppUser antes de borrar.
    # Si `user_role_association` tiene ON DELETE RESTRICT, esto fallará si está en uso.
    # Si tiene ON DELETE CASCADE para role_id, entonces se quitaría la asignación.
    # Es mejor manejarlo explícitamente.

    deleted_role_object = await crud_role.delete_role(db, role_id=role_id) # delete_role debería devolver el objeto o None
    if deleted_role_object is None: # Esto podría pasar si hay una condición de carrera, o si el rol se borró entre el get y el delete.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado o no pudo ser eliminado.")
    return deleted_role_object