# app/core/app_state.py

from typing import Optional, Dict
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_postgres.vectorstores import PGVector
from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession
import traceback

from app.config import settings
from app.crud import crud_llm_model_config
from app.llm_integrations.langchain_llm_adapter import get_langchain_llm_adapter

# --- Instancias Singleton ---
_vector_store_instance: Optional[PGVector] = None
_embedding_model_instance: Optional[SentenceTransformerEmbeddings] = None
_llm_adapter_cache: Dict[int, BaseChatModel] = {}


def initialize_global_models():
    """Se llama UNA VEZ al arrancar FastAPI. Carga los modelos pesados."""
    global _embedding_model_instance, _vector_store_instance
    
    print("APP_STATE_INIT: Cargando modelo de embeddings SBERT...")
    _embedding_model_instance = SentenceTransformerEmbeddings(
        model_name=settings.MODEL_NAME_SBERT_FOR_EMBEDDING
    )

    print("APP_STATE_INIT: Conectando al Vector Store PGVector...")
    if not settings.SYNC_DATABASE_VECTOR_URL:
        raise ValueError("SYNC_DATABASE_VECTOR_URL no está configurada.")
    
    # [SOLUCIÓN] Se usan los nombres de parámetro correctos: 'connection' y 'embeddings'
    try:
        # Usamos from_existing_index para reusar una conexión existente de forma más robusta
        _vector_store_instance = PGVector.from_existing_index(
            embedding=_embedding_model_instance,
            collection_name=settings.PGVECTOR_CHAT_COLLECTION_NAME,
            connection=settings.SYNC_DATABASE_VECTOR_URL,
            use_jsonb=True,
        )
        print("APP_STATE_INIT: Conexión a Vector Store existente exitosa.")
    except Exception as e:
        print(f"APP_STATE_INIT: Colección no encontrada o fallo ({e}). Creando una nueva...")
        _vector_store_instance = PGVector(
            connection=settings.SYNC_DATABASE_VECTOR_URL,
            embeddings=_embedding_model_instance, # 'embeddings' es el parámetro correcto
            collection_name=settings.PGVECTOR_CHAT_COLLECTION_NAME,
            use_jsonb=True,
            create_extension=False, # Asumimos que la extensión ya está en la BD
        )
        # Hacemos una inserción vacía para forzar la creación de la tabla/colección
        _vector_store_instance.add_documents([])
        print("APP_STATE_INIT: Nueva colección de Vector Store creada.")

    print("APP_STATE_INIT: Modelos globales inicializados.")

# --- Getters (sin cambios) ---
def get_embedding_model() -> SentenceTransformerEmbeddings:
    if not _embedding_model_instance: raise RuntimeError("Modelo de Embeddings no inicializado.")
    return _embedding_model_instance

def get_vector_store() -> PGVector:
    if not _vector_store_instance: raise RuntimeError("Vector Store no inicializado.")
    return _vector_store_instance

async def get_cached_llm_adapter(db: AsyncSession, model_id: int) -> BaseChatModel:
    if model_id not in _llm_adapter_cache:
        config = await crud_llm_model_config.get_llm_model_config_by_id(db, model_id)
        if not config: raise ValueError(f"Modelo LLM con ID {model_id} no encontrado.")
        _llm_adapter_cache[model_id] = get_langchain_llm_adapter(config)
    return _llm_adapter_cache[model_id]
