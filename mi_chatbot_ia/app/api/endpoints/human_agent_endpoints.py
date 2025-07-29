# app/api/endpoints/human_agent_endpoints.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.session import get_crud_db_session
from app.schemas.schemas import (
    HumanAgentCreate, HumanAgentUpdate, HumanAgentResponse,
    HumanAgentGroupCreate, HumanAgentGroupUpdate, HumanAgentGroupResponse
)
from app.crud import crud_human_agent # crud_human_agent tendrá ambas lógicas
from app.models.app_user import AppUser
from app.security.role_auth import require_roles

router = APIRouter(prefix="/api/v1/human-agent-groups", tags=["Admin - Human Agents & Groups"])
ROLES_CAN_MANAGE_HUMAN_AGENTS = ["SuperAdmin", "HRAgentManager"] # Rol ejemplo

# --- Endpoints para HumanAgentGroup ---
@router.post("/",
    response_model=HumanAgentGroupResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create Human Agent Group"
)
async def create_human_agent_group_endpoint(
    group_in: HumanAgentGroupCreate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_HUMAN_AGENTS)),
):
    existing = await crud_human_agent.get_human_agent_group_by_name(db, name=group_in.name)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Grupo de Agentes Humanos '{group_in.name}' ya existe.")
    return await crud_human_agent.create_human_agent_group(db=db, group_in=group_in)

@router.get(
    "/human-agent-groups", 
    response_model=List[HumanAgentGroupResponse],
    summary="Read All Human Agent Groups",
    tags=["Admin - Human Agents & Groups"]
)
async def read_all_human_agent_groups_endpoint(
    skip: int = 0, limit: int = 100,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_HUMAN_AGENTS)), # O roles de solo vista
):
    return await crud_human_agent.get_human_agent_groups(db, skip=skip, limit=limit)

@router.get(
    "/human-agent-groups/{group_id}", 
    response_model=HumanAgentGroupResponse,
    summary="Read Human Agent Group by ID",
    tags=["Admin - Human Agents & Groups"]
)
async def read_human_agent_group_by_id_endpoint(
    group_id: int, db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_HUMAN_AGENTS)),
):
    db_group = await crud_human_agent.get_human_agent_group_by_id(db, group_id=group_id, load_agents=True) # Cargar agentes aquí si es necesario para la respuesta
    if db_group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo de Agentes Humanos no encontrado.")
    return db_group
# ... (PUT y DELETE para HumanAgentGroup similares a los otros CRUDs) ...
@router.put(
    "/human-agent-groups/{group_id}", 
    response_model=HumanAgentGroupResponse,
    summary="Update Human Agent Group",
    tags=["Admin - Human Agents & Groups"]
)
async def update_human_agent_group_endpoint(
    group_id: int, group_in: HumanAgentGroupUpdate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_HUMAN_AGENTS))
):
    # ... (lógica de update similar a otros, verifica nombre único si cambia) ...
    db_group = await crud_human_agent.get_human_agent_group_by_id(db, group_id)
    if not db_group: raise HTTPException(status.HTTP_404_NOT_FOUND, "Grupo no encontrado")
    return await crud_human_agent.update_human_agent_group(db, db_group, group_in)

@router.delete(
    "/human-agent-groups/{group_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Human Agent Group",
    tags=["Admin - Human Agents & Groups"]
)
async def delete_human_agent_group_endpoint(
    group_id: int, db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_HUMAN_AGENTS))
):
    # ... (lógica de delete similar, verifica si está en uso por ApiClient antes de borrar) ...
    deleted = await crud_human_agent.delete_human_agent_group(db, group_id)
    if not deleted: raise HTTPException(status.HTTP_404_NOT_FOUND, "Grupo no encontrado para eliminar")
    return None


# --- Endpoints para HumanAgent ---
@router.post(
    "/human-agents", 
    response_model=HumanAgentResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create Human Agent",
    tags=["Admin - Human Agents & Groups"]
)
async def create_human_agent_endpoint(
    agent_in: HumanAgentCreate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_HUMAN_AGENTS)),
):
    existing = await crud_human_agent.get_human_agent_by_email(db, email=agent_in.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Agente Humano con email '{agent_in.email}' ya existe.")
    return await crud_human_agent.create_human_agent(db=db, agent_in=agent_in)

@router.get(
    "/human-agents", 
    response_model=List[HumanAgentResponse],
    summary="Read All Human Agents",
    tags=["Admin - Human Agents & Groups"]
)
async def read_all_human_agents_endpoint(
    skip: int = 0, limit: int = 100,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_HUMAN_AGENTS)),
):
    return await crud_human_agent.get_human_agents(db, skip=skip, limit=limit)

@router.get(
    "/human-agents/{agent_id}", 
    response_model=HumanAgentResponse,
    summary="Read Human Agent by ID",
    tags=["Admin - Human Agents & Groups"]
)
async def read_human_agent_by_id_endpoint(
    agent_id: int, db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_HUMAN_AGENTS)),
):
    db_agent = await crud_human_agent.get_human_agent_by_id(db, agent_id=agent_id, load_relations=True)
    if db_agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente Humano no encontrado.")
    return db_agent

# ... (PUT y DELETE para HumanAgent similares, con validación de email si cambia) ...
@router.put(
    "/human-agents/{agent_id}", 
    response_model=HumanAgentResponse,
    summary="Update Human Agent",
    tags=["Admin - Human Agents & Groups"]
)
async def update_human_agent_endpoint(
    agent_id: int, agent_in: HumanAgentUpdate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_HUMAN_AGENTS))
):
    # ... (lógica de update) ...
    db_agent = await crud_human_agent.get_human_agent_by_id(db, agent_id, load_relations=False) # No necesito grupos para el objeto a actualizar
    if not db_agent: raise HTTPException(status.HTTP_404_NOT_FOUND, "Agente no encontrado")
    return await crud_human_agent.update_human_agent(db, db_agent, agent_in)


@router.delete(
    "/human-agents/{agent_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Human Agent",
    tags=["Admin - Human Agents & Groups"]
)
async def delete_human_agent_endpoint(
    agent_id: int, db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_MANAGE_HUMAN_AGENTS))
):
    # ... (lógica de delete) ...
    deleted = await crud_human_agent.delete_human_agent(db, agent_id)
    if not deleted: raise HTTPException(status.HTTP_404_NOT_FOUND, "Agente no encontrado para eliminar")
    return None