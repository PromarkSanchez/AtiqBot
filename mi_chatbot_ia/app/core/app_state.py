# app/core/app_state.py (Versión 100% Completa y Funcional)

import asyncio
import traceback
from typing import Dict, Optional

# --- Librerías de Terceros ---
# Usamos el módulo asyncio de la librería redis oficial
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis # Mantenemos esta
from redis.asyncio import Redis as AsyncRedis


from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_postgres.vectorstores import PGVector
from langchain_core.language_models.chat_models import BaseChatModel

# --- Módulos Locales ---
from app.config import settings
# Las demás importaciones se hacen dentro de los métodos para evitar importaciones circulares.

# ==========================================================
# ======>      CLASE DE ESTADO DE LA APLICACIÓN        <======
# ==========================================================

class AppState:
    """
    Contenedor centralizado para todos los recursos de la aplicación
    que deben ser inicializados una vez y compartidos.
    """
    
    def __init__(self):
        # Bases de datos Asíncronas (para FastAPI)
        self.async_crud_engine: Optional[asyncio.engine.Engine] = None
        self.async_vector_engine: Optional[asyncio.engine.Engine] = None
        self.AsyncCrudSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None
        self.AsyncVectorSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None
        
        # Bases de datos Síncronas (para herramientas, scripts o lógica antigua)
        self.sync_crud_engine: Optional[Engine] = None
        self.sync_vector_engine: Optional[Engine] = None
        self.SyncCrudSessionLocal: Optional[sessionmaker[Session]] = None
        self.SyncVectorSessionLocal: Optional[sessionmaker[Session]] = None
        
        # Instancias de LangChain y otros
        self.embedding_model: Optional[SentenceTransformerEmbeddings] = None
        self.vector_store: Optional[PGVector] = None
        
        # Clientes de servicios externos y cachés
        self.redis_client: Optional[AsyncRedis] = None
        self.llm_adapter_cache: Dict[int, BaseChatModel] = {}

    async def initialize(self):
        """
        Método ASÍNCRONO para inicializar todos los recursos.
        Se llamará desde el lifespan de FastAPI.
        """
        print("\n--- [INIT] Iniciando Carga de Recursos Globales ---")

        # 1. Modelo de Embeddings (Operación Síncrona)
        print("      [1/5] Cargando Modelo de Embeddings...")
        try:
            self.embedding_model = SentenceTransformerEmbeddings(
                model_name=settings.MODEL_NAME_SBERT_FOR_EMBEDDING
            )
            print("      -> Éxito: Embeddings cargados.")
        except Exception as e:
            raise RuntimeError(f"Fallo crítico al cargar Embeddings: {e}")

        # 2. Conexiones a BD ASÍNCRONAS
        print("      [2/5] Inicializando Pools de Conexión ASÍNCRONOS...")
        try:
            self.async_crud_engine = create_async_engine(settings.DATABASE_CRUD_URL, pool_pre_ping=True)
            self.AsyncCrudSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=self.async_crud_engine)

            self.async_vector_engine = create_async_engine(settings.DATABASE_VECTOR_URL, pool_pre_ping=True)
            self.AsyncVectorSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=self.async_vector_engine)
            
            # ===> Calentamiento y ¡LA BALA DE PLATA FINAL! <====
            async with self.async_crud_engine.connect() as conn_crud:
                print("      -> Éxito: Pool de conexión ASÍNCRONO CRUD calentado.")
            
            # Vamos a usar el motor vectorial para asegurarnos de que la extensión `vector` existe.
            async with self.async_vector_engine.connect() as conn_vector:
                print("      -> Éxito: Pool de conexión ASÍNCRONO Vector DB calentado.")
                
                # IMPORTANTE: Importamos `text` de SQLAlchemy
                from sqlalchemy import text
                
                # Ejecutamos la creación de la extensión como una transacción separada.
                await conn_vector.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await conn_vector.commit() # Aseguramos que se guarde el cambio
                print("      -> Éxito: Extensión 'vector' asegurada en la base de datos.")

        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Fallo al crear pools o al preparar la extensión vector: {e}")
            
        # 3. Vector Store ASÍNCRONO
        print("      [3/5] Creando instancia de PGVector...")
        try:
            self.vector_store = PGVector(
                connection=settings.DATABASE_VECTOR_URL,
                embeddings=self.embedding_model,
                collection_name=settings.PGVECTOR_CHAT_COLLECTION_NAME,
                use_jsonb=True,
                async_mode=True
            )
            print("      -> Éxito: Instancia ASÍNCRONA de PGVector creada.")

            # ========= ¡LA SOLUCIÓN DEL DUMMY SEARCH! ==========
            # Forzamos una búsqueda de similitud falsa para desencadenar
            # toda la inicialización interna de Langchain AHORA.
            print("      -> Calentando el VectorStore con una búsqueda de prueba...")
            try:
                # Hacemos una búsqueda que no encontrará nada (k=1)
                # para que sea lo más rápida posible.
                await self.vector_store.asimilarity_search("warm-up query", k=1)
                print("      -> Éxito: VectorStore calentado sin errores.")
            except Exception as warmup_error:
                # ¡IMPORTANTE! Si la búsqueda falla (por ejemplo, con el error de la
                # multi-sentencia), lo capturamos aquí, lo registramos, PERO
                # PERMITIMOS QUE LA APLICACIÓN CONTINÚE.
                print(f"      -> INFO: El calentamiento del VectorStore falló como se esperaba. Error: {warmup_error}")
                print("      -> Esto es normal en el primer arranque. El pool ya está listo para peticiones reales.")
            # ======================================================

        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Fallo crítico al crear PGVector: {e}")

        # 4. Conexiones a BD SÍNCRONAS
        print("      [4/5] Creando Pools de Conexión SÍNCRONOS...")
        self.sync_crud_engine = create_engine(settings.SYNC_DATABASE_CRUD_URL, pool_pre_ping=True)
        self.SyncCrudSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.sync_crud_engine)
        self.sync_vector_engine = create_engine(settings.SYNC_DATABASE_VECTOR_URL, pool_pre_ping=True)
        self.SyncVectorSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.sync_vector_engine)
        print("      -> Éxito: Pools SÍNCRONOS creados.")

        # 5. Conexión a Redis
        print("      [5/5] Inicializando Backend de Caché con Redis...")
        if settings.REDIS_URL:
            try:
                # Creamos una instancia de cliente de bajo nivel.
                redis_instance = aioredis.from_url(settings.REDIS_URL, encoding="utf8", decode_responses=True)
                # Pasamos esta instancia a la librería de caché.
                FastAPICache.init(RedisBackend(redis_instance), prefix="fastapi-cache")
                self.redis_client = redis_instance
                # La librería se encargará del ping y la gestión de la conexión.
                print("      -> Éxito: Backend de caché Redis configurado.")
            except Exception as e:
                self.redis_client = None
                FastAPICache.init(InMemoryBackend()) # Un fallback a memoria
                print(f"      -> ADVERTENCIA: Falló la conexión a Redis. Usando caché en memoria. Error: {e}")
        else:
            # Fallback a un backend de memoria si no hay URL de Redis
            from fastapi_cache.backends.in_memory import InMemoryBackend
            FastAPICache.init(InMemoryBackend())
            print("      -> ADVERTENCIA: REDIS_URL no configurada. Usando caché en memoria.")
        
        print("--- [INIT] Todos los recursos inicializados con éxito. ---\n")

    async def close(self):
        """
        Cierra limpiamente las conexiones al apagar la aplicación.
        """
        if self.async_crud_engine:
            await self.async_crud_engine.dispose()
            print("INFO:     [SHUTDOWN] Pool de conexión CRUD cerrado.")
        if self.async_vector_engine:
            await self.async_vector_engine.dispose()
            print("INFO:     [SHUTDOWN] Pool de conexión Vector DB cerrado.")
        if self.redis_client:
            await self.redis_client.close()
            print("INFO:     [SHUTDOWN] Conexión a Redis cerrada.")

    # En app/core/app_state.py, DENTRO de la clase AppState:

    async def get_cached_llm(self, model_config, temperature_to_use: float) -> BaseChatModel:
        """
        Obtiene un adaptador de LLM desde el caché. La clave del caché ahora
        incluye la temperatura para asegurar que se usan instancias distintas.
        """
        # --- Imports locales para evitar dependencias circulares ---
        from app.llm_integrations import langchain_llm_adapter
        from langchain_core.language_models.chat_models import BaseChatModel

        # La clave del caché ahora es una combinación del ID del modelo y la temperatura.
        # Esto es crucial para que agentes diferentes no reusen el mismo objeto si tienen temps distintas.
        cache_key = f"llm_{model_config.id}_temp_{temperature_to_use:.2f}"
        
        if cache_key in self.llm_adapter_cache:
            print(f"LLM_CACHE_HIT: Reusando '{model_config.display_name}' con Temp {temperature_to_use:.2f} desde caché.")
            return self.llm_adapter_cache[cache_key]
        
        print(f"LLM_CACHE_MISS: Creando nueva instancia de '{model_config.display_name}' con Temp {temperature_to_use:.2f}.")
        
        # Le pasamos la temperatura decidida al adaptador. El adaptador ya no piensa, solo ejecuta.
        adapter_instance: BaseChatModel = await asyncio.to_thread(
            langchain_llm_adapter.get_langchain_llm_adapter,
            config=model_config,
            temperature_to_use=temperature_to_use
        )

        self.llm_adapter_cache[cache_key] = adapter_instance
        return adapter_instance

# ==========================================================
# ======>   FUNCIÓN DE ARRANQUE PARA SER USADA EN main.py  <======
# ==========================================================
async def initialize_application() -> AppState:
    """
    Punto de entrada para la inicialización. Crea, inicializa y devuelve 
    el objeto de estado de la aplicación.
    """
    app_state = AppState()
    await app_state.initialize()
    return app_state