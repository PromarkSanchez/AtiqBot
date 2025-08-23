# app/crud/crud_app_user.py
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from app.models.app_user import AppUser, AuthMethod
from app.models.role import Role 
from app.schemas.schemas import AppUserLocalCreate, AppUserUpdate
from app.utils.security_utils import encrypt_data, decrypt_data, get_password_hash
from app.config import settings

# === Funciones de Lectura (GET) ===
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

# === Funciones de Creación (CREATE) ===
async def create_local_user(db: AsyncSession, user_in: AppUserLocalCreate) -> AppUser:
    hashed_password = get_password_hash(user_in.password)
    user_data = user_in.model_dump(exclude={"password", "role_ids"})
    db_user = AppUser(**user_data, hashed_password=hashed_password, auth_method=AuthMethod.LOCAL)
    
    if user_in.role_ids:
        roles_result = await db.execute(select(Role).filter(Role.id.in_(user_in.role_ids)))
        db_user.roles = roles_result.scalars().all()
        
    db.add(db_user)
    await db.flush()
    await db.refresh(db_user, attribute_names=['roles'])
    return db_user

# === Función de Actualización (UPDATE) - LA SOLUCIÓN FINAL ===
async def update_user(db: AsyncSession, db_user: AppUser, user_in: AppUserUpdate) -> AppUser:
    """
    Actualiza un usuario modificando directamente sus atributos.
    SQLAlchemy detectará los cambios y los guardará gracias al commit final de la sesión.
    """
    update_data = user_in.model_dump(exclude_unset=True)

    # 1. Itera sobre los datos del payload y actualiza el objeto 'db_user'
    for field, value in update_data.items():
        if field == "roles_ids":
            # Maneja la relación de roles por separado
            if not value:
                db_user.roles = []
            else:
                roles_result = await db.execute(select(Role).filter(Role.id.in_(value)))
                db_user.roles = roles_result.scalars().all()
        else:
            # Para campos simples (mfa_enabled, is_active_local, etc.)
            setattr(db_user, field, value)
    
    # 2. Añade el objeto a la sesión para asegurarse de que SQLAlchemy lo rastrea.
    db.add(db_user)
    
    # 3. Sincroniza y recarga para que el objeto devuelto esté 100% actualizado.
    await db.flush()
    await db.refresh(db_user)
    await db.refresh(db_user, attribute_names=['roles'])
    
    return db_user

# === Funciones de MFA ===
async def set_app_user_mfa_status(db: AsyncSession, db_user: AppUser, enabled: bool) -> AppUser:
    db_user.mfa_enabled = enabled
    if not enabled:
        db_user.mfa_secret_encrypted = None
    db.add(db_user)
    return db_user

async def update_app_user_mfa_secret(db: AsyncSession, db_user: AppUser, mfa_secret_plain: str) -> AppUser:
    if not settings.FERNET_KEY:
        raise ValueError("FERNET_KEY no está configurado.")
    db_user.mfa_secret_encrypted = encrypt_data(mfa_secret_plain)
    db.add(db_user)
    return db_user

async def get_decrypted_mfa_secret(db_user: AppUser) -> Optional[str]:
    if db_user.mfa_secret_encrypted:
        return decrypt_data(db_user.mfa_secret_encrypted)
    return None

# === Función de Eliminación (DELETE) ===
async def delete_user(db: AsyncSession, user_id: int) -> bool:
    user_to_delete = await get_app_user_by_id(db, user_id)
    if not user_to_delete:
        raise ValueError(f"Usuario con ID {user_id} no encontrado para eliminar.")
    await db.delete(user_to_delete)
    await db.flush()
    return True