# app/crud/crud_admin_menu.py
from typing import Optional, List, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.models.admin_panel import AdminPanelMenu, AdminRoleMenuPermission
from app.models.app_user import AppUser # Necesario para la función principal
from app.schemas.schemas import AdminPanelMenuCreate, AdminPanelMenuUpdate

# --- CRUD para AdminPanelMenu ---

async def get_menu_by_id(db: AsyncSession, menu_id: int) -> Optional[AdminPanelMenu]:
    result = await db.execute(select(AdminPanelMenu).filter(AdminPanelMenu.id == menu_id))
    return result.scalars().first()

async def get_menu_by_name(db: AsyncSession, name: str) -> Optional[AdminPanelMenu]:
    result = await db.execute(select(AdminPanelMenu).filter(AdminPanelMenu.name == name))
    return result.scalars().first()

async def get_all_menus(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[AdminPanelMenu]:
    result = await db.execute(select(AdminPanelMenu).order_by(AdminPanelMenu.display_order, AdminPanelMenu.name).offset(skip).limit(limit))
    return result.scalars().all()

async def create_menu(db: AsyncSession, menu_in: AdminPanelMenuCreate) -> AdminPanelMenu:
    db_menu = AdminPanelMenu(**menu_in.model_dump())
    db.add(db_menu)
    await db.commit()
    await db.refresh(db_menu)
    return db_menu

async def update_menu(db: AsyncSession, db_menu: AdminPanelMenu, menu_in: AdminPanelMenuUpdate) -> AdminPanelMenu:
    update_data = menu_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_menu, key, value)
    db.add(db_menu)
    await db.commit()
    await db.refresh(db_menu)
    return db_menu

async def delete_menu(db: AsyncSession, menu_id: int) -> Optional[AdminPanelMenu]:
    db_menu = await get_menu_by_id(db, menu_id=menu_id)
    if db_menu:
        await db.delete(db_menu)
        await db.commit()
    return db_menu


# --- Lógica de Permisos de Menú-Rol ---

async def get_permission(db: AsyncSession, role_id: int, menu_id: int) -> Optional[AdminRoleMenuPermission]:
    result = await db.execute(select(AdminRoleMenuPermission).filter_by(role_id=role_id, menu_id=menu_id))
    return result.scalars().first()
    
async def assign_menu_to_role(db: AsyncSession, role_id: int, menu_id: int) -> AdminRoleMenuPermission:
    # Evitar duplicados
    existing_perm = await get_permission(db, role_id=role_id, menu_id=menu_id)
    if existing_perm:
        return existing_perm

    db_perm = AdminRoleMenuPermission(role_id=role_id, menu_id=menu_id, can_view=True)
    db.add(db_perm)
    await db.commit()
    await db.refresh(db_perm)
    return db_perm
    
async def remove_menu_from_role(db: AsyncSession, role_id: int, menu_id: int) -> bool:
    statement = delete(AdminRoleMenuPermission).where(
        AdminRoleMenuPermission.role_id == role_id,
        AdminRoleMenuPermission.menu_id == menu_id
    )
    result = await db.execute(statement)
    await db.commit()
    return result.rowcount > 0

async def get_menus_for_role(db: AsyncSession, role_id: int) -> List[AdminPanelMenu]:
    statement = (
        select(AdminPanelMenu)
        .join(AdminRoleMenuPermission)
        .where(AdminRoleMenuPermission.role_id == role_id)
        .order_by(AdminPanelMenu.display_order, AdminPanelMenu.name)
    )
    result = await db.execute(statement)
    return result.scalars().all()


# --- FUNCIÓN CLAVE PARA EL ENDPOINT /me/menus ---

async def get_authorized_menus_for_user(db: AsyncSession, user: AppUser) -> List[AdminPanelMenu]:
    """
    Obtiene los menús únicos a los que un usuario tiene acceso a través de CUALQUIERA de sus roles.
    """
    if not user.roles:
        return []

    user_role_ids: List[int] = [role.id for role in user.roles]

    statement = (
        select(AdminPanelMenu)
        .join(AdminRoleMenuPermission, AdminPanelMenu.id == AdminRoleMenuPermission.menu_id)
        .where(AdminRoleMenuPermission.role_id.in_(user_role_ids), AdminRoleMenuPermission.can_view == True)
        .distinct()
        .order_by(AdminPanelMenu.display_order, AdminPanelMenu.name)
    )
    
    result = await db.execute(statement)
    return result.scalars().all()