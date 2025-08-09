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

async def update_app_user_mfa_secret(db: AsyncSession, db_user: AppUser, mfa_secret_plain: str) -> AppUser:
    if not settings.FERNET_KEY: # Es buena práctica chequear aquí también
        print("ERROR CRUD (AppUser): FERNET_KEY no configurado al intentar encriptar MFA secret.")
        raise ValueError("FERNET_KEY no está configurado.")
    # Llamando a encrypt_data SIN la clave porque tu security_utils.py la toma globalmente.
    # Si hubieras modificado security_utils para que encrypt_data TOME la clave:
    # db_user.mfa_secret_encrypted = encrypt_data(mfa_secret_plain, settings.FERNET_KEY)
    db_user.mfa_secret_encrypted = encrypt_data(mfa_secret_plain) # Asume que encrypt_data usa global Fernet

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def set_app_user_mfa_status(db: AsyncSession, db_user: AppUser, enabled: bool) -> AppUser:
    db_user.mfa_enabled = enabled
    if not enabled: 
        db_user.mfa_secret_encrypted = None
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def get_decrypted_mfa_secret(db_user: AppUser) -> Optional[str]:
    if db_user.mfa_secret_encrypted: # No necesitas settings.FERNET_KEY aquí si decrypt_data lo usa globalmente
        # decrypted_value = decrypt_data(db_user.mfa_secret_encrypted, settings.FERNET_KEY)
        decrypted_value = decrypt_data(db_user.mfa_secret_encrypted) # Asume que decrypt_data usa global Fernet
        if decrypted_value == "[DATO ENCRIPTADO INVÁLIDO O ERROR DE DESENCRIPTACIÓN]": # El string que devuelve tu decrypt_data en error
            print(f"ERROR CRUD (AppUser): Falló la desencriptación del secreto MFA para usuario {db_user.username_ad}")
            return None
        return decrypted_value
    return None

async def update_app_user_roles(db: AsyncSession, db_user: AppUser, role_ids: List[int]) -> AppUser:
    if not role_ids: # Si se pasa una lista vacía, quitar todos los roles
        db_user.roles = []
    else:
        new_roles_q_result = await db.execute(select(Role).filter(Role.id.in_(role_ids)))
        new_roles_list_from_db = new_roles_q_result.scalars().all()
        
        if len(new_roles_list_from_db) != len(set(role_ids)):
             # Para encontrar cuáles faltan (opcional, para mejor mensaje de error)
            # found_ids = {r.id for r in new_roles_list_from_db}
            # missing_ids = set(role_ids) - found_ids
            # print(f"ADVERTENCIA CRUD (AppUser): IDs de rol no encontrados: {missing_ids}")
            raise ValueError("Uno o más IDs de rol proporcionados no existen en la BD.")
            
        db_user.roles = new_roles_list_from_db
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    # Cargar las relaciones actualizadas es crucial aquí si la sesión original ya no está activa o para estar seguros
    return await get_app_user_by_id(db, db_user.id) if db_user.id else db_user

 

 