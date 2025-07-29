# app/crud/crud_app_user.py

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete # --> Añadimos 'delete' de sqlalchemy

from sqlalchemy.orm import selectinload

# --- Modelos de la Base de Datos ---
from app.models.app_user import AppUser, AuthMethod
from app.models.role import Role 

# --- Schemas de Pydantic ---
# CORRECCIÓN 1: AÑADIMOS 'AppUserUpdate' a la importación
from app.schemas.schemas import AppUserLocalCreate, AppUserUpdate
from app.schemas.admin_auth import AppUserUpdateByAdmin

# --- Utilidades y Configuración ---
from app.utils.security_utils import encrypt_data, decrypt_data, get_password_hash
from app.config import settings
from app.crud.crud_role import get_role_by_name

# === Funciones de Lectura (GET) ===
# ... (Estas funciones ya estaban bien, las dejo para que el archivo esté completo) ...
async def get_app_user_by_id(db: AsyncSession, user_id: int) -> Optional[AppUser]:
    result = await db.execute(select(AppUser).options(selectinload(AppUser.roles)).filter(AppUser.id == user_id))
    return result.scalars().first()
async def get_app_user_by_username_ad(db: AsyncSession, username_ad: str) -> Optional[AppUser]:
    result = await db.execute(select(AppUser).options(selectinload(AppUser.roles)).filter(AppUser.username_ad == username_ad))
    return result.scalars().first()
async def get_app_user_by_email(db: AsyncSession, email: str) -> Optional[AppUser]:
    if not email: return None
    result = await db.execute(select(AppUser).filter(AppUser.email == email))
    return result.scalars().first()
async def get_all_app_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[AppUser]:
    result = await db.execute(select(AppUser).options(selectinload(AppUser.roles)).offset(skip).limit(limit).order_by(AppUser.id))
    return result.scalars().unique().all()

async def delete_user(db: AsyncSession, user_id: int) -> Optional[AppUser]:
    """
    Busca un usuario por su ID y lo elimina de la base de datos.
    Devuelve el objeto del usuario eliminado si se encuentra, si no None.
    """
    user_to_delete = await get_app_user_by_id(db, user_id)
    
    if not user_to_delete:
        return None
        
    await db.delete(user_to_delete)
    await db.commit()
    
    return user_to_delete
# === Funciones de Creación (CREATE) ===
# ... (Esta función ya estaba bien) ...
async def create_local_user(db: AsyncSession, user_in: AppUserLocalCreate) -> AppUser:
    hashed_password = get_password_hash(user_in.password)
    user_data = user_in.model_dump(exclude={"password", "role_ids"})
    db_user = AppUser(**user_data, hashed_password=hashed_password, auth_method=AuthMethod.LOCAL)
    if user_in.role_ids:
        roles_result = await db.execute(select(Role).filter(Role.id.in_(user_in.role_ids)))
        roles_list = roles_result.scalars().all()
        if len(roles_list) != len(set(user_in.role_ids)):
            raise ValueError("Uno o más IDs de rol no son válidos.")
        db_user.roles = roles_list
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return await get_app_user_by_id(db, db_user.id)

async def create_app_user_internal(db: AsyncSession, username_ad: str, **kwargs) -> AppUser:
    # ... (Tu función interna, la dejo como está)
    return AppUser()


# === Funciones de Actualización (UPDATE) ===

# --- LA NUEVA FUNCIÓN PARA EL ENDPOINT ---
async def update_user(db: AsyncSession, db_user: AppUser, user_in: AppUserUpdate) -> AppUser:
    """Función genérica para actualizar los datos de un usuario."""
    update_data = user_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "role_ids":
            await update_app_user_roles(db, db_user, value)
        else:
            setattr(db_user, field, value)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return await get_app_user_by_id(db, db_user.id)

async def update_app_user_roles(db: AsyncSession, db_user: AppUser, role_ids: List[int]) -> AppUser:
    """Actualiza solo los roles de un usuario."""
    if role_ids is not None: # Permite pasar una lista vacía para quitar todos los roles
        roles_result = await db.execute(select(Role).filter(Role.id.in_(role_ids)))
        db_user.roles = roles_result.scalars().all()
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

# --- TU FUNCIÓN ANTIGUA, AHORA CORREGIDA ---
async def update_app_user_details_by_admin(db: AsyncSession, db_user_to_update: AppUser, user_update_data: AppUserUpdateByAdmin) -> AppUser:
    """Función de actualización existente, ahora corregida."""
    update_data = user_update_data.model_dump(exclude_unset=True)

    if 'email' in update_data:
        db_user_to_update.email = update_data['email']
    if 'full_name' in update_data:
        db_user_to_update.full_name = update_data['full_name']
    if 'is_active_local' in update_data:
        db_user_to_update.is_active_local = update_data['is_active_local']
    
    # CORRECCIÓN 2: Esta línea es la que tenía el error de tipeo. Debe llamar a 'set_app_user_mfa_status'.
    if 'mfa_enabled' in update_data and update_data['mfa_enabled'] != db_user_to_update.mfa_enabled:
        db_user_to_update = await set_app_user_mfa_status(db, db_user_to_update, update_data['mfa_enabled'])
    
    if 'role_ids' in update_data:
        db_user_to_update = await update_app_user_roles(db, db_user_to_update, update_data['role_ids'])
        
    await db.commit()
    await db.refresh(db_user_to_update)
    return db_user_to_update


# === Funciones de MFA (no necesitan cambios) ===

async def set_app_user_mfa_status(db: AsyncSession, db_user: AppUser, enabled: bool) -> AppUser:
    # Asegúrate de tener esta función si `update_app_user_details_by_admin` la llama.
    db_user.mfa_enabled = enabled
    if not enabled:
        db_user.mfa_secret_encrypted = None
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user