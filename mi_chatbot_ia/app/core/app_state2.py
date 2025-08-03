# app/core/app_state.py (VERSIÓN FINAL CON AISLAMIENTO TOTAL Y SIN DUPLICADOS)

from typing import Optional, Dict
import redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
import traceback

from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_postgres.vectorstores import PGVector
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings
from app.crud import crud_llm_model_config
from app.llm_integrations.langchain_llm_adapter import get_langchain_llm_adapter

# --- Instancias Singleton Globales ---
# Las únicas dos instancias que necesitas para la base vectorial
_sync_vector_store: Optional[PGVector] = None
_async_vector_store: Optional[PGVector] = None

_embedding_model_instance: Optional[SentenceTransformerEmbeddings] = None
_llm_adapter_cache: Dict[int, BaseChatModel] = {}
_redis_instance: Optional[redis.Redis] = None


def initialize_global_models():
    """Se llama UNA VEZ al arrancar. Crea instancias separadas para sync y async."""
    global _embedding_model_instance, _sync_vector_store, _async_vector_store, _redis_instance
    
    print("APP_STATE_INIT: Cargando embeddings...")
    _embedding_model_instance = SentenceTransformerEmbeddings(
        model_name=settings.MODEL_NAME_SBERT_FOR_EMBEDDING
    )

    # --- 1. Inicialización del Vector Store SÍNCRONO (para tu lógica original) ---
    print("APP_STATE_INIT: Creando instancia SÍNCRONA de PGVector...")
    if not settings.SYNC_DATABASE_VECTOR_URL: raise ValueError("SYNC_DATABASE_VECTOR_URL es requerida.")
    try:
        # No se le pasa _async_engine aquí para que sea puramente síncrona
        _sync_vector_store = PGVector(
            connection=settings.SYNC_DATABASE_VECTOR_URL,
            embeddings=_embedding_model_instance, collection_name=settings.PGVECTOR_CHAT_COLLECTION_NAME,
            use_jsonb=True, create_extension=False
        )
        print("APP_STATE_INIT: Instancia SÍNCRONA creada con éxito.")
    except Exception as e:
        print(f"ERROR CRÍTICO (SYNC): {e}")
        raise e

    # --- 2. Inicialización del Vector Store ASÍNCRONO (para el futuro o pruebas) ---
    print("APP_STATE_INIT: Creando instancia ASÍNCRONA de PGVector...")
    if not settings.DATABASE_VECTOR_URL: print("ADVERTENCIA: DATABASE_VECTOR_URL no configurada, instancia async no creada.")
    else:
        try:
            # Creamos una segunda instancia completamente separada
            _async_vector_store = PGVector(
                connection=settings.SYNC_DATABASE_VECTOR_URL,
                embeddings=_embedding_model_instance, collection_name=settings.PGVECTOR_CHAT_COLLECTION_NAME,
                use_jsonb=True, create_extension=False
            )
            # Y a esta sí le adjuntamos el motor async
            _async_vector_store._async_engine = create_async_engine(settings.DATABASE_VECTOR_URL)
            print("APP_STATE_INIT: Instancia ASÍNCRONA creada con éxito.")
        except Exception as e:
            print(f"ERROR CRÍTICO (ASYNC): {e}")
            # No levantamos un error aquí para que la app pueda seguir funcionando en modo sync
            _async_vector_store = None
    
    # --- 3. Lógica de Redis (se queda igual) ---
    print("APP_STATE_INIT: Intentando conectar a Redis Cache...")
    if not settings.REDIS_URL:
        print("ADVERTENCIA: REDIS_URL no configurada. Caché desactivado.")
    else:
        try:
            _redis_instance = redis.from_url(settings.REDIS_URL, decode_responses=True)
            _redis_instance.ping()
            print("APP_STATE_INIT: Conexión a Redis exitosa.")
        except Exception as e:
            _redis_instance = None
            print(f"ADVERTENCIA: Falló conexión a Redis. Error: {e}")

    print("APP_STATE_INIT: Todas las inicializaciones completadas.")


# --- Nuevos Getters Separados ---
def get_sync_vector_store() -> PGVector:
    """Devuelve la instancia SÍNCRONA, segura para usar en threads."""
    if not _sync_vector_store: raise RuntimeError("Vector Store SÍNCRONO no inicializado.")
    return _sync_vector_store

def get_async_vector_store() -> PGVector:
    """Devuelve la instancia ASÍNCRONA, segura para usar con await."""
    if not _async_vector_store: raise RuntimeError("Vector Store ASÍNCRONO no inicializado.")
    return _async_vector_store


# --- Getters Antiguos que se mantienen ---
def get_embedding_model() -> SentenceTransformerEmbeddings:
    if not _embedding_model_instance: raise RuntimeError("Modelo de Embeddings no inicializado.")
    return _embedding_model_instance

def get_redis_client() -> Optional[redis.Redis]:
    return _redis_instance

async def get_cached_llm_adapter(db: AsyncSession, model_id: int) -> BaseChatModel:
    # ... (esta función no necesita cambios)
    if model_id not in _llm_adapter_cache:
        config = await crud_llm_model_config.get_llm_model_config_by_id(db, model_id)
        if not config: raise ValueError(f"Modelo LLM con ID {model_id} no encontrado.")
        _llm_adapter_cache[model_id] = get_langchain_llm_adapter(config)
    return _llm_adapter_cache[model_id]