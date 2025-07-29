# app/crud/crud_human_agent.py
from typing import Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.human_agent import HumanAgent as HumanAgentModel, HumanAgentGroup as HAGroupModel
from app.schemas.schemas import ( # Ajusta desde tu app/schemas.py
    HumanAgentCreate, HumanAgentUpdate,
    HumanAgentGroupCreate, HumanAgentGroupUpdate
)

# --- CRUD para HumanAgent ---
async def create_human_agent(db: AsyncSession, agent_in: HumanAgentCreate) -> HumanAgentModel:
    # Separar group_ids de los datos del modelo principal
    group_ids = agent_in.group_ids
    agent_data = agent_in.model_dump(exclude={"group_ids"})
    
    db_agent = HumanAgentModel(**agent_data)
    
    if group_ids:
        stmt_groups = select(HAGroupModel).filter(HAGroupModel.id.in_(group_ids))
        result_groups = await db.execute(stmt_groups)
        groups_to_associate = result_groups.scalars().all()
        db_agent.agent_groups.extend(groups_to_associate)

    db.add(db_agent)
    await db.commit()
    await db.refresh(db_agent)
    return await get_human_agent_by_id(db, db_agent.id) # Devolver con grupos cargados

async def get_human_agent_by_id(db: AsyncSession, agent_id: int, load_relations: bool = True) -> Optional[HumanAgentModel]:
    stmt = select(HumanAgentModel).filter(HumanAgentModel.id == agent_id)
    if load_relations:
        stmt = stmt.options(selectinload(HumanAgentModel.agent_groups))
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_human_agent_by_email(db: AsyncSession, email: str, load_relations: bool = False) -> Optional[HumanAgentModel]:
    stmt = select(HumanAgentModel).filter(HumanAgentModel.email == email)
    if load_relations:
        stmt = stmt.options(selectinload(HumanAgentModel.agent_groups))
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_human_agents(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[HumanAgentModel]:
    stmt = select(HumanAgentModel).options(selectinload(HumanAgentModel.agent_groups)).offset(skip).limit(limit).order_by(HumanAgentModel.full_name)
    result = await db.execute(stmt)
    return result.scalars().all()

async def update_human_agent(db: AsyncSession, db_agent: HumanAgentModel, agent_in: HumanAgentUpdate) -> HumanAgentModel:
    update_data = agent_in.model_dump(exclude={"group_ids"}, exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_agent, field, value)

    if agent_in.group_ids is not None: # Permite enviar lista vacía para desasociar todos
        db_agent.agent_groups.clear() # Limpiar antes de añadir los nuevos
        if agent_in.group_ids:
            stmt_groups = select(HAGroupModel).filter(HAGroupModel.id.in_(agent_in.group_ids))
            result_groups = await db.execute(stmt_groups)
            groups_to_associate = result_groups.scalars().all()
            db_agent.agent_groups.extend(groups_to_associate)
            
    await db.commit()
    await db.refresh(db_agent)
    return await get_human_agent_by_id(db, db_agent.id) # Devolver con grupos cargados

async def delete_human_agent(db: AsyncSession, agent_id: int) -> Optional[HumanAgentModel]:
    db_agent = await get_human_agent_by_id(db, agent_id, load_relations=False)
    if db_agent:
        await db.delete(db_agent) # SQLAlchemy debería manejar la tabla de asociación gracias a ondelete='CASCADE' o limpiando la relación
        await db.commit()
        return db_agent
    return None

# --- CRUD para HumanAgentGroup ---
async def create_human_agent_group(db: AsyncSession, group_in: HumanAgentGroupCreate) -> HAGroupModel:
    db_group = HAGroupModel(**group_in.model_dump())
    db.add(db_group)
    await db.commit()
    await db.refresh(db_group)
    return db_group

async def get_human_agent_group_by_id(db: AsyncSession, group_id: int, load_agents: bool = False) -> Optional[HAGroupModel]:
    stmt = select(HAGroupModel).filter(HAGroupModel.id == group_id)
    if load_agents:
        stmt = stmt.options(selectinload(HAGroupModel.agents))
    result = await db.execute(stmt)
    return result.scalars().first()
    
async def get_human_agent_group_by_name(db: AsyncSession, name: str) -> Optional[HAGroupModel]:
    result = await db.execute(select(HAGroupModel).filter(HAGroupModel.name == name))
    return result.scalars().first()

async def get_human_agent_groups(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[HAGroupModel]:
    stmt = select(HAGroupModel).offset(skip).limit(limit).order_by(HAGroupModel.name)
    result = await db.execute(stmt)
    # No cargamos los agentes en la lista por defecto para evitar sobrecarga.
    # Si necesitas la lista de agentes, podrías tener otro parámetro 'load_agents_in_list'.
    return result.scalars().all()

async def update_human_agent_group(db: AsyncSession, db_group: HAGroupModel, group_in: HumanAgentGroupUpdate) -> HAGroupModel:
    update_data = group_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_group, field, value)
    await db.commit()
    await db.refresh(db_group)
    return db_group

async def delete_human_agent_group(db: AsyncSession, group_id: int) -> Optional[HAGroupModel]:
    db_group = await get_human_agent_group_by_id(db, group_id)
    if db_group:
        # Al eliminar un grupo, la tabla de asociación se encarga por 'ondelete=CASCADE'.
        # O SQLAlchemy limpiará la relación si los 'agents' fueron cargados y la relación tiene cascade delete-orphan.
        await db.delete(db_group)
        await db.commit()
        return db_group
    return None