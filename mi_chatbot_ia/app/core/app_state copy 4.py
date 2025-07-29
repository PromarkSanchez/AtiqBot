# --- ARCHIVO COMPLETO Y DEFINITIVO: app/core/app_state.py ---

import redis
import traceback
import asyncio
from typing import Optional, Dict

# Importamos lo necesario de SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# Importamos los Embeddings correctos
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_postgres.vectorstores import PGVector
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings
from app.models.llm_model_config import LLMModelConfig
from app.llm_integrations import langchain_llm_adapter

# --- Instancias Singleton Globales ---
_sync_vector_store: Optional[PGVector] = None
_async_vector_store: Optional[PGVector] = None
_embedding_model_instance: Optional[SentenceTransformerEmbeddings] = None
_llm_adapter_cache: Dict[int, BaseChatModel] = {}
_redis_instance: Optional[redis.Redis] = None


# --- LA FUNCIÓN DE INICIALIZACIÓN FINAL, COMPLETA Y CORRECTA ---
def initialize_global_models():
    """
    Se llama UNA VEZ al arrancar. Inicializa todos los componentes globales
    usando el método directo y fundamental, evitando los bugs de la librería.
    """
    global _embedding_model_instance, _sync_vector_store, _async_vector_store, _redis_instance
    
    print("\n--- [INIT] Iniciando Carga de Componentes Globales ---")
    
    # 1. Modelo de Embeddings
    print("      [1/4] Cargando Modelo de Embeddings...")
    try:
        _embedding_model_instance = SentenceTransformerEmbeddings(
            model_name=settings.MODEL_NAME_SBERT_FOR_EMBEDDING
        )
        print("      -> Éxito: Embeddings cargados.")
    except Exception as e:
        raise RuntimeError(f"Fallo crítico al cargar Embeddings: {e}")

    # 2. Vector Store Síncrono (EL PATRÓN SIMPLE Y CORRECTO)
    print("      [2/4] Creando instancia SÍNCRONA de PGVector...")
    if not settings.SYNC_DATABASE_VECTOR_URL:
        print("    -> ADVERTENCIA: SYNC_DATABASE_VECTOR_URL no configurada.")
    else:
        try:
            # ¡LA VERDAD! Creamos el motor de SQLAlchemy primero...
            sync_engine = create_engine(settings.SYNC_DATABASE_VECTOR_URL)
            # ... y se lo pasamos al constructor con 'connection'. Y 'embeddings'.
            _sync_vector_store = PGVector(
                connection=sync_engine,
                embeddings=_embedding_model_instance,
                collection_name=settings.PGVECTOR_CHAT_COLLECTION_NAME,
                use_jsonb=True
            )
            print("      -> Éxito: Instancia SÍNCRONA creada.")
        except Exception as e:
            print("      -> ERROR FATAL: No se pudo conectar al Vector Store SÍNCRONO.")
            traceback.print_exc()
            raise RuntimeError(f"Fallo al crear PGVector síncrono: {e}")

    # 3. Vector Store ASÍNCRONO (EL MISMO PATRÓN ROBUSTO)
    print("      [3/4] Creando instancia ASÍNCRONA de PGVector...")
    if not settings.DATABASE_VECTOR_URL:
        print("    -> ADVERTENCIA: DATABASE_VECTOR_URL no configurada.")
    else:
        try:
            # Creamos el motor asíncrono...
            async_engine = create_async_engine(settings.DATABASE_VECTOR_URL)
            
            # ...y se lo pasamos al MISMO constructor, que detectará que es asíncrono.
            _async_vector_store = PGVector(
                connection=async_engine,
                embeddings=_embedding_model_instance,
                collection_name=settings.PGVECTOR_CHAT_COLLECTION_NAME,
                use_jsonb=True,
                async_mode=True
            )
            print("      -> Éxito: Instancia ASÍNCRONA de PGVector creada.")
        except Exception as e:
            print("      -> ERROR FATAL: No se pudo inicializar o verificar el Vector Store ASÍNCRONO.")
            traceback.print_exc()
            raise RuntimeError(f"Fallo crítico al crear PGVector asíncrono: {e}")

    # 4. Redis (sin cambios, tu versión estaba bien)
    print("      [4/4] Conectando a Redis Cache...")
    if settings.REDIS_URL:
        try:
            _redis_instance = redis.from_url(settings.REDIS_URL, decode_responses=True)
            _redis_instance.ping()
            print("    -> Éxito: Conexión a Redis establecida.")
        except Exception as e:
            _redis_instance = None
            print(f"    -> ADVERTENCIA: Falló conexión a Redis. Error: {e}")
    else:
        print("    -> ADVERTENCIA: REDIS_URL no configurada. Caché desactivado.")
    
    print("--- [INIT] Todos los componentes inicializados con éxito. ---\n")


# --- Getters (completos para que no haya dudas) ---
def get_sync_vector_store() -> PGVector:
    if _sync_vector_store is None: raise RuntimeError("El Vector Store SÍNCRONO no fue inicializado.")
    return _sync_vector_store

def get_async_vector_store() -> PGVector:
    if _async_vector_store is None: raise RuntimeError("El Vector Store ASÍNCRONO no fue inicializado.")
    return _async_vector_store

def get_redis_client() -> Optional[redis.Redis]:
    return _redis_instance
    
def get_embedding_model() -> SentenceTransformerEmbeddings:
    if not _embedding_model_instance: raise RuntimeError("Modelo de Embeddings no inicializado.")
    return _embedding_model_instance

async def get_cached_llm_adapter(db_crud: AsyncSession, model_config: LLMModelConfig) -> BaseChatModel:
    global _llm_adapter_cache
    model_id = model_config.id
    if model_id in _llm_adapter_cache:
        return _llm_adapter_cache[model_id]
        
    adapter_instance = langchain_llm_adapter.get_langchain_llm_adapter(config=model_config)
    _llm_adapter_cache[model_id] = adapter_instance
    return adapter_instance