# app/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession # type: ignore
from sqlalchemy.orm import sessionmaker, declarative_base # type: ignore # declarative_base lo usaremos por separado ahora
from sqlalchemy import inspect as sqlalchemy_inspect # <--- AÑADE ESTA LÍNEA (o `from sqlalchemy.inspection import inspect as sqlalchemy_inspect`)

from app.config import settings

# --- Motor y Sesión para la Base de Datos de CRUDs (chatbot_db) ---
async_engine_crud = create_async_engine(
    settings.DATABASE_CRUD_URL, 
    echo=True, # Puedes poner a False si se vuelve muy verboso
    future=True
)
AsyncSessionLocal_CRUD = sessionmaker(
    autocommit=False, autoflush=False, bind=async_engine_crud,
    class_=AsyncSession, expire_on_commit=False
)
Base_CRUD = declarative_base() # Base para modelos CRUD

async def get_crud_db_session() -> AsyncSession:
    async with AsyncSessionLocal_CRUD() as session:
        try:
            yield session
            
            # ----- DEBUG SQLAlchemy Dirty Objects -----
            if session.dirty:
                print(f"DEBUG: Session is dirty before explicit commit. Dirty objects: {len(session.dirty)}")
                for obj in session.dirty:
                    print(f"  - Dirty Object: {type(obj).__name__} (ID: {obj.id if hasattr(obj, 'id') else 'N/A'})")
                    obj_state = sqlalchemy_inspect(obj)
                    for attr in obj_state.attrs:
                        if attr.history.has_changes():
                            print(f"    - Changed attr: {attr.key}, history: {attr.history}")
                            if attr.key == 'settings':
                                print(f"      - Current settings value type: {type(getattr(obj, attr.key))}")
            # ----- FIN DEBUG -----

            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# --- Motor y Sesión para la Base de Datos de Vectores (ChatBotVector) ---
async_engine_vector = create_async_engine(
    settings.DATABASE_VECTOR_URL,
    echo=True, # Puedes poner a False si se vuelve muy verboso
    future=True
)
AsyncSessionLocal_Vector = sessionmaker(
    autocommit=False, autoflush=False, bind=async_engine_vector,
    class_=AsyncSession, expire_on_commit=False
)
Base_Vector = declarative_base() # Base para modelos de Vectores

async def get_vector_db_session() -> AsyncSession:
    async with AsyncSessionLocal_Vector() as session:
        try:
            yield session
             # await session.commit() # <--- TEMPORALMENTE COMENTADO PARA DEBUG DE GETs
            print("DEBUG: Commit en get_crud_db_session OMITIDO TEMPORALMENTE.")
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()