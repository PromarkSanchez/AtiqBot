# mi_chatbot_ia/init_db.py
import asyncio
from sqlalchemy import text # type: ignore
from app.models.db_connection_config import DatabaseConnectionConfig, SupportedDBType # <--- NUEVO
from app.models.db_connection_config import DatabaseConnectionConfig, SupportedDBType
from app.models.document_source_config import DocumentSourceConfig, SupportedDocSourceType # <--- NUEVO
from app.models.context_definition import ContextDefinition, ContextMainType # <--- NUEVO
from app.models.role import Role
from app.models.app_user import AppUser
 

from app.db.session import (
    async_engine_crud, Base_CRUD,
    async_engine_vector, Base_Vector
)

# --- ¡IMPORTANTE! Asegúrate que TODOS los modelos estén importados ANTES de usar sus Bases ---
from app.models.user import User                     # Para Base_CRUD
from app.models.interaction_log import InteractionLog  # <--- ¡ASEGURA QUE ESTÉ IMPORTADO AQUÍ! Para Base_CRUD
from app.models.api_client import ApiClient # <--- NUEVO


from app.models.document import Document, DocumentChunk # Para Base_Vector  
# ---------------------------------------------------------------------------------------

async def initialize_database(engine, base_metadata, db_name, enable_vector_extension=False):
    print(f"Inicializando base de datos: {db_name}")
    async with engine.connect() as conn:
        if enable_vector_extension:
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                await conn.commit()
                print(f"Extensión 'vector' asegurada en {db_name}.")
            except Exception as e:
                print(f"Advertencia al asegurar extensión 'vector' en {db_name}: {e}")
                await conn.rollback()
        
        # print(f"Eliminando tablas existentes en {db_name} (si aplica)...")
        # await conn.run_sync(base_metadata.drop_all) 

        print(f"Creando tablas en {db_name}...")
        # Aquí es donde base_metadata (ej. Base_CRUD.metadata) necesita "conocer" todos sus modelos.
        await conn.run_sync(base_metadata.create_all)
        await conn.commit()
    
    print(f"Tablas para {db_name} creadas/actualizadas.")
    # await engine.dispose() # No queremos dispose aquí si la app sigue corriendo y lo necesita.
                            # El dispose está bien si este script es puramente standalone para inicialización.
                            # Dado que es parte del setup, y lo llamamos al inicio, vamos a mover el dispose al final de main()

async def main():
    # Inicializar la base de datos de CRUDs
    await initialize_database(async_engine_crud, Base_CRUD.metadata, "chatbot_db (CRUDs)")

    # Inicializar la base de datos de Vectores
    await initialize_database(async_engine_vector, Base_Vector.metadata, "ChatBotVector (Vectores)", enable_vector_extension=True)

    # Dispose engines al final si el script es standalone
    print("Cerrando conexiones de los motores de base de datos...")
    await async_engine_crud.dispose()
    await async_engine_vector.dispose()
    print("Conexiones cerradas.")


if __name__ == "__main__":
    print("Ejecutando inicialización para AMBAS bases de datos...")
    asyncio.run(main())