# app/api/v1/admin/admin_menus_api.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_crud_db_session
from app.schemas.schemas import (
    AdminPanelMenuCreate, AdminPanelMenuUpdate, AdminPanelMenuResponse,
    AdminRoleMenuPermissionCreate, AdminRoleMenuPermissionResponse,
    AuthorizedMenuResponse
)
from app.crud import crud_admin_menu, crud_role
from app.models.app_user import AppUser
from app.security.role_auth import require_roles

# Mismos roles de tu roles_api.py para consistencia
ROLE_SUPERADMIN = ["SuperAdmin"]
ROLES_CAN_VIEW = ["SuperAdmin", "ContextEditor", "LogViewer"] # Roles que pueden ver y usar el panel

MENU_GESTION_MENU = "Gestión de Menús"

# --- ROUTER PRINCIPAL PARA MENUS ---
router = APIRouter(
    prefix="/api/v1/admin/menus",
    tags=["Admin - Menu Management"],
)

@router.post("/", response_model=AdminPanelMenuResponse, status_code=status.HTTP_201_CREATED, summary="Crear un nuevo item de menú")
async def create_new_menu_item(
    menu_in: AdminPanelMenuCreate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_GESTION_MENU))
):
    """Solo SuperAdmin puede definir los menús del sistema."""
    existing_menu = await crud_admin_menu.get_menu_by_name(db, name=menu_in.name)
    if existing_menu:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"El menú '{menu_in.name}' ya existe.")
    return await crud_admin_menu.create_menu(db, menu_in)

@router.get("/", response_model=List[AdminPanelMenuResponse], summary="Obtener todos los items de menú definibles")
async def get_all_menu_items(
    skip: int = 0, limit: int = 100,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_GESTION_MENU))
):
    """Solo SuperAdmin puede listar todos los menús configurables."""
    return await crud_admin_menu.get_all_menus(db, skip=skip, limit=limit)

@router.put("/{menu_id}", response_model=AdminPanelMenuResponse, summary="Actualizar un item de menú")
async def update_menu_item(
    menu_id: int, menu_in: AdminPanelMenuUpdate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_GESTION_MENU))
):
    db_menu = await crud_admin_menu.get_menu_by_id(db, menu_id)
    if not db_menu:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menú no encontrado.")
    return await crud_admin_menu.update_menu(db, db_menu=db_menu, menu_in=menu_in)

@router.delete("/{menu_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar un item de menú")
async def delete_menu_item(
    menu_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_GESTION_MENU))
):
    deleted_menu = await crud_admin_menu.delete_menu(db, menu_id)
    if not deleted_menu:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menú no encontrado.")
    return None

# --- ROUTER PARA GESTIONAR PERMISOS ---
router_perms = APIRouter(
    prefix="/api/v1/admin/roles/{role_id}/menus",
    tags=["Admin - Menu Management"],
)

@router_perms.get("/", response_model=List[AdminPanelMenuResponse], summary="Obtener menús asignados a un rol")
async def get_menus_for_role(
    role_id: int, db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_GESTION_MENU))
):
    db_role = await crud_role.get_role_by_id(db, role_id)
    if not db_role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rol no encontrado.")
    return await crud_admin_menu.get_menus_for_role(db, role_id=role_id)

@router_perms.post("/", response_model=AdminRoleMenuPermissionResponse, summary="Asignar un menú a un rol")
async def assign_menu_permission_to_role(
    role_id: int, perm_in: AdminRoleMenuPermissionCreate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_GESTION_MENU))
):
    db_role = await crud_role.get_role_by_id(db, role_id)
    if not db_role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rol no encontrado.")
    db_menu = await crud_admin_menu.get_menu_by_id(db, perm_in.menu_id)
    if not db_menu:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menú no encontrado.")
    return await crud_admin_menu.assign_menu_to_role(db, role_id=role_id, menu_id=perm_in.menu_id)
    
@router_perms.delete("/{menu_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Quitar permiso de un menú a un rol")
async def remove_menu_permission_from_role(
    role_id: int, menu_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_GESTION_MENU))
):
    success = await crud_admin_menu.remove_menu_from_role(db, role_id=role_id, menu_id=menu_id)
    if not success:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permiso no encontrado para eliminar.")
    return None


# --- ENDPOINT CLAVE PARA EL FRONTEND ---
router_me = APIRouter(
    prefix="/api/v1/admin/me",
    tags=["Admin - User Profile"],
)

@router_me.get("/menus", response_model=List[AuthorizedMenuResponse], summary="Obtener los menús autorizados para el usuario logueado")
async def get_my_authorized_menus(
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_VIEW))
):
    """
    Endpoint principal para el frontend. Tras el login, se llama a esta ruta
    para obtener la lista de menús que el panel de administración debe renderizar
    para el usuario actual.
    """
    return await crud_admin_menu.get_authorized_menus_for_user(db, user=current_user)