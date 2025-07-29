# app/crud/crud_role.py
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession # type: ignore
from sqlalchemy.future import select # type: ignore

from app.models.role import Role
from app.schemas.admin_auth import RoleCreate, RoleUpdate # Asumiendo que están en admin_auth.py # type: ignore

async def get_role_by_id(db: AsyncSession, role_id: int) -> Optional[Role]:
    result = await db.execute(select(Role).filter(Role.id == role_id))
    return result.scalars().first()

async def get_role_by_name(db: AsyncSession, name: str) -> Optional[Role]:
    result = await db.execute(select(Role).filter(Role.name == name))
    return result.scalars().first()

async def get_roles(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Role]:
    result = await db.execute(select(Role).offset(skip).limit(limit))
    return result.scalars().all()

async def create_role(db: AsyncSession, role_in: RoleCreate) -> Role:
    db_role = Role(name=role_in.name, description=role_in.description)
    db.add(db_role)
    await db.commit()
    await db.refresh(db_role)
    return db_role

async def update_role(db: AsyncSession, db_role: Role, role_in: RoleUpdate) -> Role:
    update_data = role_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_role, key, value)
    db.add(db_role)
    await db.commit()
    await db.refresh(db_role)
    return db_role

async def delete_role(db: AsyncSession, role_id: int) -> Optional[Role]:
    db_role = await get_role_by_id(db, role_id)
    if db_role:
        # Aquí podrías añadir lógica para verificar si el rol está en uso antes de borrar,
        # o manejarlo a nivel de BD con ON DELETE (aunque eso podría no ser ideal para roles).
        # Por ahora, borrado directo.
        await db.delete(db_role)
        await db.commit()
        return db_role
    return None