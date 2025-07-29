# app/crud/crud_db_connection.py
from typing import Optional, List, Any

# --- Para las funciones ASÍNCRONAS ---
from sqlalchemy.ext.asyncio import AsyncSession # type: ignore
from sqlalchemy.future import select as future_select # Renombrado para evitar colisión # type: ignore

# --- Para la nueva función SÍNCRONA ---
from sqlalchemy import create_engine, select as sync_select # Import síncrono de select # type: ignore
from sqlalchemy.orm import Session as SyncSession # Session síncrona # type: ignore
from app.config import settings # Para la URL de la BD síncrona

from app.models.db_connection_config import DatabaseConnectionConfig as DBConnModel
from app.schemas.schemas import DatabaseConnectionCreate, DatabaseConnectionUpdate 
from app.utils.security_utils import encrypt_data, decrypt_data

# --- Funciones ASÍNCRONAS (las que ya tenías) ---

async def create_db_connection(db: AsyncSession, conn_in: DatabaseConnectionCreate) -> DBConnModel:
    encrypted_pass = None
    if conn_in.password:
        encrypted_pass = encrypt_data(conn_in.password)
    
    db_conn_obj = DBConnModel(
        name=conn_in.name,
        description=conn_in.description,
        db_type=conn_in.db_type,
        host=conn_in.host,
        port=conn_in.port,
        database_name=conn_in.database_name,
        username=conn_in.username,
        encrypted_password=encrypted_pass,
        extra_params=conn_in.extra_params
    )
    db.add(db_conn_obj)
    await db.commit()
    await db.refresh(db_conn_obj)
    return db_conn_obj

async def get_db_connection_by_id(db: AsyncSession, conn_id: int) -> Optional[DBConnModel]:
    result = await db.execute(future_select(DBConnModel).filter(DBConnModel.id == conn_id))
    return result.scalars().first()

async def get_db_connection_by_name(db: AsyncSession, name: str) -> Optional[DBConnModel]:
    result = await db.execute(future_select(DBConnModel).filter(DBConnModel.name == name))
    return result.scalars().first()
    
async def get_db_connections(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[DBConnModel]:
    result = await db.execute(future_select(DBConnModel).offset(skip).limit(limit))
    return result.scalars().all()

async def update_db_connection(
    db: AsyncSession, 
    db_conn_obj: DBConnModel,
    conn_in: DatabaseConnectionUpdate
) -> DBConnModel:
    update_data = conn_in.model_dump(exclude_unset=True)

    if "password" in update_data and update_data["password"] is not None:
        update_data["encrypted_password"] = encrypt_data(update_data["password"])
        del update_data["password"]
    elif "password" in update_data and update_data["password"] is None:
        del update_data["password"]

    for field, value in update_data.items():
        setattr(db_conn_obj, field, value)
    
    db.add(db_conn_obj)
    await db.commit()
    await db.refresh(db_conn_obj)
    return db_conn_obj

async def delete_db_connection(db: AsyncSession, conn_id: int) -> Optional[DBConnModel]:
    db_conn_obj = await get_db_connection_by_id(db, conn_id)
    if db_conn_obj:
        await db.delete(db_conn_obj)
        await db.commit()
        return db_conn_obj
    return None

async def get_decrypted_password(db_conn_obj: DBConnModel) -> Optional[str]:
    if db_conn_obj and db_conn_obj.encrypted_password:
        # Asumo que decrypt_data es una función síncrona. Si es asíncrona, necesitas `await`.
        return decrypt_data(db_conn_obj.encrypted_password)
    return None

# --- Nueva función SÍNCRONA ---

# Crear un engine síncrono global o una función para obtenerlo
_sync_crud_engine = None

def get_sync_crud_engine():
    global _sync_crud_engine
    if _sync_crud_engine is None:
        if not settings.SYNC_DATABASE_CRUD_URL:
            raise ValueError("SYNC_DATABASE_CRUD_URL no está configurada en settings.py")
        _sync_crud_engine = create_engine(settings.SYNC_DATABASE_CRUD_URL)
    return _sync_crud_engine

def get_db_connection_by_id_sync(conn_id: int) -> Optional[DBConnModel]:
    """
    Obtiene una configuración de conexión a BD por su ID usando una sesión SÍNCRONA.
    Esta función es SÍNCRONA y debe ser llamada desde código síncrono o envuelta
    en asyncio.to_thread si se llama desde código asíncrono.
    """
    engine = get_sync_crud_engine()
    with SyncSession(engine) as session: # Usar SyncSession para una sesión síncrona
        # Usar sync_select (alias de sqlalchemy.select)
        stmt = sync_select(DBConnModel).filter(DBConnModel.id == conn_id)
        result = session.execute(stmt)
        db_conn = result.scalars().first()
        # Para que las relaciones (si las hubiera y fueran necesarias aquí) se carguen,
        # necesitarías configurar opciones de carga (ej. selectinload) en el stmt
        # o acceder a ellas dentro de la sesión para que se auto-carguen si la config lo permite.
        # Sin embargo, para el uso en sql_tools, solo necesitas los atributos directos.
        return db_conn