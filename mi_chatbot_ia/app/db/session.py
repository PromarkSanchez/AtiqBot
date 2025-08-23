# app/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

# --- Motor y Sesión para la Base de Datos de CRUDs (chatbot_db) ---
async_engine_crud = create_async_engine(settings.DATABASE_CRUD_URL, echo=True)

AsyncSessionLocal_CRUD = async_sessionmaker(
    bind=async_engine_crud,
    class_=AsyncSession,
    expire_on_commit=False
)

Base_CRUD = declarative_base()

async def get_crud_db_session() -> AsyncSession:
    """
    Dependencia de FastAPI que provee una sesión y gestiona la transacción.
    Hace COMMIT si todo va bien, y ROLLBACK si hay un error.
    """
    async with AsyncSessionLocal_CRUD() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# --- Motor y Sesión para la Base de Datos de Vectores (si la usas) ---
async_engine_vector = create_async_engine(settings.DATABASE_VECTOR_URL, echo=True)
AsyncSessionLocal_Vector = async_sessionmaker(bind=async_engine_vector, class_=AsyncSession, expire_on_commit=False)
Base_Vector = declarative_base()

async def get_vector_db_session() -> AsyncSession:
    async with AsyncSessionLocal_Vector() as session:
        yield session