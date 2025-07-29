# app/crud/crud_user.py
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession  # type: ignore
from sqlalchemy.future import select  # type: ignore
from sqlalchemy.orm import selectinload # Para cargar relaciones si las tuviéramos  # type: ignore

from app.models.user import User as UserModel # Renombramos para evitar conflicto con el schema
from app.schemas.schemas import UserCreate, UserUpdate # <--- MODIFICADO para usar solo los de entrada

# Para crear un usuario, necesitaremos un schema Pydantic que defina los datos de entrada.
# Por ahora, vamos a crear una versión simple para el DNI y rol.
# Idealmente, esto estaría en app/schemas.py
from pydantic import BaseModel, constr # type: ignore

# LÍNEA CORRECTA (EJEMPLO)
# --- ¡Estas importaciones son las que corregimos! ---
from app.models.role import Role # Modelo Role que tiene el `name` y el `id`
from app.models.context_permission import RoleContextPermission # La tabla de unión


class UserCreateSchema(BaseModel):
    dni: constr(min_length=8, max_length=20) # type: ignore
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "user"

class UserUpdateSchema(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

#async def create_user(db: AsyncSession, user_in: UserCreateSchema) -> UserModel:
async def create_user(db: AsyncSession, user_in: UserCreate) -> UserModel: # <--- MODIFICADO


    """
    Crea un nuevo usuario en la base de datos.
    """
    # Aquí podríamos añadir lógica para hashear contraseñas si las tuviéramos.
    db_user = UserModel(
        dni=user_in.dni,
        email=user_in.email,
        full_name=user_in.full_name,
        role=user_in.role,
        is_active=True # Por defecto, activo
    )
    db.add(db_user)
    await db.commit() # Commit individual para esta operación (también manejado por get_db_session)
    await db.refresh(db_user) # Refrescar para obtener el ID y otros valores generados por la BD
    return db_user

async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[UserModel]:
    """
    Obtiene un usuario por su ID.
    """
    result = await db.execute(select(UserModel).filter(UserModel.id == user_id))
    return result.scalars().first()

async def get_user_by_dni(db: AsyncSession, dni: str) -> Optional[UserModel]:
    """
    Obtiene un usuario por su DNI.
    """
    result = await db.execute(select(UserModel).filter(UserModel.dni == dni))
    return result.scalars().first()

async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[UserModel]:
    """
    Obtiene una lista de usuarios con paginación.
    """
    result = await db.execute(select(UserModel).offset(skip).limit(limit))
    return result.scalars().all()

# async def update_user(db: AsyncSession, user_db_obj: UserModel, user_in: UserUpdateSchema) -> UserModel:
async def update_user(db: AsyncSession, user_db_obj: UserModel, user_in: UserUpdate) -> UserModel: # <--- MODIFICADO

    """
    Actualiza un usuario existente.
    `user_db_obj` es el objeto User ya obtenido de la BD.
    `user_in` son los nuevos datos (un schema Pydantic).
    """
    update_data = user_in.model_dump(exclude_unset=True) # Solo actualiza los campos proporcionados
    for field, value in update_data.items():
        setattr(user_db_obj, field, value)
    
    db.add(user_db_obj) # SQLAlchemy es inteligente y sabe que esto es una actualización
    await db.commit()
    await db.refresh(user_db_obj)
    return user_db_obj

async def delete_user(db: AsyncSession, user_id: int) -> Optional[UserModel]:
    """
    Elimina un usuario por su ID.
    Devuelve el usuario eliminado o None si no se encontró.
    """
    user_to_delete = await get_user_by_id(db, user_id)
    if user_to_delete:
        await db.delete(user_to_delete)
        await db.commit()
        return user_to_delete
    return None


# --- ¡AQUÍ ESTÁ LA FUNCIÓN CORREGIDA Y FINAL! ---
async def get_contexts_for_user_dni(db: AsyncSession, dni: str) -> List[int]:
    """
    Busca el rol del usuario final por su DNI y devuelve la lista de IDs de
    contexto permitidos para ese rol. VERSIÓN CORREGIDA.
    """
    print(f"CRUD_USER: Buscando permisos para el DNI: {dni}")

    # Este statement empieza desde UserModel y hace JOINs secuenciales,
    # lo cual evita la duplicación de alias.
    stmt = (
        select(RoleContextPermission.context_definition_id)
        .select_from(UserModel)  # Empezamos explícitamente desde la tabla de usuarios
        .where(UserModel.dni == dni)
        .join(Role, Role.name == UserModel.role)
        .join(RoleContextPermission, RoleContextPermission.role_id == Role.id)
    )

    result = await db.execute(stmt)
    allowed_ids = result.scalars().all()
    
    print(f"CRUD_USER: Permisos para DNI {dni} encontrados: {allowed_ids}")
    return allowed_ids
# Podríamos añadir más funciones, como get_user_by_email, etc.