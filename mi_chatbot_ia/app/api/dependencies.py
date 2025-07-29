# app/api/dependencies.py

from typing import AsyncGenerator, Optional
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_postgres.vectorstores import PGVector
from redis.asyncio import Redis as AsyncRedis


# Importamos la clase AppState para anotaciones de tipo (type hinting)
# Esto evita importaciones circulares.
from app.core.app_state import AppState


def get_app_state(request: Request) -> AppState:
    """
    Dependencia de FastAPI para obtener el objeto AppState del estado de la aplicación.
    """
    return request.app.state.app_state


# ==========================================================
# ======>    DEPENDENCIAS ASÍNCRONAS (para FastAPI)      <======
# ==========================================================

async def get_crud_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependencia para inyectar una sesión ASÍNCRONA para la base de datos CRUD.
    Abre una sesión, la entrega al endpoint (`yield`), y se asegura de cerrarla al final.
    """
    app_state = get_app_state(request)
    async with app_state.AsyncCrudSessionLocal() as session:
        yield session

async def get_vector_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependencia para inyectar una sesión ASÍNCRONA para la base de datos VECTOR.
    """
    app_state = get_app_state(request)
    async with app_state.AsyncVectorSessionLocal() as session:
        yield session
        
def get_vector_store(request: Request) -> PGVector:
    """
    Dependencia para inyectar la instancia pre-inicializada del Vector Store ASÍNCRONO.
    """
    app_state = get_app_state(request)
    if not app_state.vector_store:
        raise RuntimeError("El Vector Store no fue inicializado correctamente en el arranque.")
    return app_state.vector_store

def get_redis_client(request: Request) -> Optional[AsyncRedis]:
    """
    Dependencia para inyectar el cliente de Redis asíncrono.
    """
    app_state = get_app_state(request)
    return app_state.redis_client