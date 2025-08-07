# app/core/app_state.py (Versión Corregida para Producción en Render)

import asyncio
import traceback
from typing import Dict, Optional

# --- Librerías de Terceros ---
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker, AsyncSession
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_postgres.vectorstores import PGVector
from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy import text # <<< ¡AÑADE ESTA IMPORTACIÓN!

# --- Módulos Locales ---
from app.config import settings

class AppState:
    def __init__(self):
        self.async_crud_engine: Optional[AsyncEngine] = None
        self.async_vector_engine: Optional[AsyncEngine] = None
        self.AsyncCrudSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None
        self.embedding_model: Optional[SentenceTransformerEmbeddings] = None
        self.vector_store: Optional[PGVector] = None
        self.redis_client: Optional[AsyncRedis] = None
        self.llm_adapter_cache: Dict[str, BaseChatModel] = {}

    async def initialize(self):
        print("\n--- [INIT] Iniciando Carga de Recursos Globales (Modo Producción Ligero) ---")

        # 1. Modelo de Embeddings (Operación Síncrona en CPU, está bien aquí)
        print("      [1/4] Cargando Modelo de Embeddings...")
        try:
            # Para hacer el arranque aún más rápido, podemos mover esto a un to_thread
            self.embedding_model = await asyncio.to_thread(
                SentenceTransformerEmbeddings, model_name=settings.MODEL_NAME_SBERT_FOR_EMBEDDING
            )
            print("      -> Éxito: Embeddings cargados.")
        except Exception as e:
            raise RuntimeError(f"Fallo crítico al cargar Embeddings: {e}")

        # 2. Conexiones a BD ASÍNCRONAS y Redis (Creación y Verificación)
        print("      [2/4] Creando y verificando pools de conexión...")
        try:
            self.async_crud_engine = create_async_engine(settings.DATABASE_CRUD_URL, pool_pre_ping=True)
            self.AsyncCrudSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=self.async_crud_engine)
            
            self.async_vector_engine = create_async_engine(settings.DATABASE_VECTOR_URL, pool_pre_ping=True)

            # ... (el código de Redis se queda igual) ...
            if settings.REDIS_URL:
                self.redis_client = AsyncRedis.from_url(settings.REDIS_URL, encoding="utf8", decode_responses=True)
                await self.redis_client.ping() # Verificación asíncrona
                FastAPICache.init(RedisBackend(self.redis_client), prefix="fastapi-cache")
                print("      -> Éxito: Conexión a Redis verificada.")
            else:
                from fastapi_cache.backends.in_memory import InMemoryBackend
                FastAPICache.init(InMemoryBackend())
                print("      -> ADVERTENCIA: No hay REDIS_URL. Usando caché en memoria.")

            # --- Verificación de Conexión ---
            print("      -> Verificando conexión a DB CRUD...")
            async with self.async_crud_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            print("      -> Éxito: Conexión a DB CRUD verificada.")

            print("      -> Verificando conexión a DB Vector...")
            async with self.async_vector_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            print("      -> Éxito: Conexión a DB Vector verificada.")


        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Fallo al crear o verificar pools de conexión: {e}")
            
        # 3. Vector Store ASÍNCRONO (¡Solo la instanciación!)
        print("      [3/4] Creando instancia de PGVector (modo perezoso)...")
        try:
            self.vector_store = PGVector(
                connection=settings.SYNC_DATABASE_VECTOR_URL, # <--- NOTA: PGVector a menudo usa la síncrona para setup
                embeddings=self.embedding_model,
                collection_name=settings.PGVECTOR_CHAT_COLLECTION_NAME,
                use_jsonb=True,
                # async_mode=True # No necesitamos esto si lo usamos a través de as_retriever o métodos 'a'
            )
            print("      -> Éxito: Instancia de PGVector creada. La conexión se establecerá en la primera petición.")
        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Fallo crítico al crear la instancia de PGVector: {e}")

        # 4. Caché de LLMs (inicialmente vacío)
        print("      [4/4] Inicializando caché de LLMs...")
        self.llm_adapter_cache = {}
        print("      -> Éxito: Caché de LLMs lista.")
        
        print("--- [INIT] Inicialización de bajo nivel completada. Aplicación lista para arrancar. ---\n")

    async def close(self):
        print("    [AppState] Cerrando pools de conexión...")
        tasks = []
        if self.async_crud_engine: tasks.append(self.async_crud_engine.dispose())
        if self.async_vector_engine: tasks.append(self.async_vector_engine.dispose())
        if self.redis_client: tasks.append(self.redis_client.close())
        await asyncio.gather(*tasks)
        print("    [AppState] Pools de conexión cerrados.")

    # ... Tu método get_cached_llm() se queda exactamente igual, es perfecto. ...
    async def get_cached_llm(self, model_config, temperature_to_use: float) -> BaseChatModel:
        # Tu código aquí (no necesita cambios)
        from app.llm_integrations import langchain_llm_adapter
        cache_key = f"llm_{model_config.id}_temp_{temperature_to_use:.2f}"
        if cache_key in self.llm_adapter_cache:
            return self.llm_adapter_cache[cache_key]
        adapter_instance = await asyncio.to_thread(
            langchain_llm_adapter.get_langchain_llm_adapter,
            config=model_config,
            temperature_to_use=temperature_to_use
        )
        self.llm_adapter_cache[cache_key] = adapter_instance
        return adapter_instance


async def initialize_application() -> AppState:
    app_state = AppState()
    await app_state.initialize()
    return app_state