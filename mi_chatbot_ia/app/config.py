# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List, Any
from dotenv import load_dotenv
import os

# Carga las variables de entorno desde el archivo .env
load_dotenv()

class Settings(BaseSettings):
    """
    Clase que centraliza todas las configuraciones de la aplicación.
    Lee variables de entorno y las valida con Pydantic.
    """
    
    # --- URLs de Bases de Datos ---
    DATABASE_CRUD_URL: str
    DATABASE_VECTOR_URL: str
    SYNC_DATABASE_CRUD_URL: str
    SYNC_DATABASE_VECTOR_URL: str
    # +++++++++++++ NUEVAS LÍNEAS PARA AÑADIR +++++++++++++
    # --- Configuración General de la Aplicación y CORS ---
    ENVIRONMENT: str = "production" # Puede ser "development" o "production"
    
    # Los orígenes permitidos para conectarse a tu API.
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:8000", "http://localhost:5173",
        "http://3.227.128.241:5173", "http://172.31.35.254:5173",
        "https://upch-test.blackboard.com", "https://admin-ia.cayetano.pe",
        "https://admin-ia-back.cayetano.pe", "https://cayetano.pe",
        "http://172.17.100.75",
        "http://127.0.0.1:5500",
        "http://localhost:4173",
        "http://127.0.0.1:5500",
        "https://atiqtec.com"
       
      
    ]

    # ==========================================================
    # ======>        NUEVA CONFIGURACIÓN DE REDIS        <======
    # ==========================================================
    # URL de conexión a Redis. Se puede sobreescribir con una variable de entorno.
    # REDIS_URL: str = "redis://localhost:6379"
    REDIS_URL : str ="redis://localhost:6379"

    # Tiempo de expiración para las entradas del caché en segundos (1 hora por defecto).
    CACHE_EXPIRATION_SECONDS: int = 3600
    # ==========================================================

    # --- Configuración LLM y Embeddings ---
    GEMINI_API_KEY: Optional[str] = None
    DEFAULT_LLM_TEMPERATURE: float = 0.7
    MODEL_NAME_SBERT_FOR_EMBEDDING: str = "all-MiniLM-L6-v2"
    
    # --- Configuración General de la Aplicación ---
    LANGCHAIN_VERBOSE: bool = True
    PGVECTOR_CHAT_COLLECTION_NAME: str = "chatbot_knowledge_base_v1"
    CHAT_HISTORY_TABLE_NAME: str = "chat_message_history_v2"
    FERNET_KEY: str # Requerido en .env para encriptación.
    
    # --- Active Directory (Admin Auth) ---
    AD_SERVER_URL: Optional[str] = "ldap://172.17.100.2"
    AD_BASE_DN: Optional[str] = "dc=upch,dc=edu,dc=pe"
    AD_UPN_SUFFIX: Optional[str] = "upch.edu.pe"
    AD_DOMAIN_NT: Optional[str] = "upchnt"
    AD_USERNAME_AD_ATTRIBUTE_TO_STORE: str = "sAMAccountName"
    AD_TIMEOUT_SECONDS: int = 10
    
    # --- JWT (Admin Auth) ---
    JWT_SECRET_KEY: str # Requerido en .env
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8
    JWT_PRE_MFA_TOKEN_EXPIRE_MINUTES: int = 5
    
    # --- MFA (Admin Auth) ---
    MFA_APP_NAME: str = "ChatBotIA"
    
    # --- Configuración Específica del Chatbot ---
    DW_CONTEXT_CONFIG_NAME: str = "Esquema Data Warehouse Principal"
    SQL_INTENT_KEYWORDS: List[str] = ["describe la tabla", "columnas de", "esquema de", "total de registros", "promedio de"]
    DW_TABLE_PREFIXES_FOR_INTENT: List[str] = ["AGR_", "DIM_", "FCT_", "FACT_"]
    MAX_RETRIEVED_CHUNKS_RAG: int = 8
    CHAT_HISTORY_WINDOW_SIZE_RAG: int = 6
    CHAT_HISTORY_WINDOW_SIZE_SQL: int = 0

    # --- PROMPTS POR DEFECTO / FALLBACK ---


# Dentro de la clase Settings en app/config.py

    DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE: str = (
        "Tu tarea es reformular la Pregunta de Seguimiento para que sea una pregunta completa y autocontenida. Debes IGNORAR COMPLETAMENTE el Historial de Chat y concentrarte ÚNICA Y EXCLUSIVAMENTE en la última pregunta del usuario.\n"
        "El historial es solo para contexto mínimo, no para mezclar temas.\n\n"
        "REGLA DE ORO: Si la 'Pregunta de Seguimiento' introduce un TEMA NUEVO (como cambiar de 'logaritmos' a 'ecuaciones'), tu respuesta DEBE SER solo sobre ese TEMA NUEVO.\n\n"
        "Historial del Chat (ignorar para reformular):\n"
        "{chat_history}\n\n"
        "Pregunta de Seguimiento (CONCÉNTRATE AQUÍ):\n"
        "{question}\n\n"
        "Pregunta Independiente Resultante:"
    )


    DEFAULT_RAG_DOCS_QA_TEMPLATE: str = (
        "Eres un Asistente Virtual. Usa el siguiente contexto para responder a la pregunta. "
        "Si no sabes la respuesta basándote en el contexto, simplemente di que no tienes esa información, "
        "no intentes inventar una respuesta. Sé conciso y directo.\n\n"
        "Contexto:\n{context}\n\n"
        "Pregunta:\n{question}\n\n"
        "Respuesta Útil:"
    )
    
    # Pydantic-settings config
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

    # Constructor



settings = Settings()



if __name__ == "__main__":
    print("--- Configuraciones Cargadas desde app/config.py ---")
    print(f"  PROJECT_NAME: {settings.PROJECT_NAME if hasattr(settings, 'PROJECT_NAME') else 'No Definido'}")
    print(f"  DATABASE_CRUD_URL: {'...' + settings.DATABASE_CRUD_URL[-10:] if settings.DATABASE_CRUD_URL else 'No Definido'}")
    print(f"  GEMINI_API_KEY: {'Presente' if settings.GEMINI_API_KEY else 'Ausente (Normal si se usan otros proveedores)'}")
    print(f"  FERNET_KEY: {'Presente' if settings.FERNET_KEY else 'Ausente (CRÍTICO para MFA)'}")
    print(f"  JWT_SECRET_KEY: {'Presente' if settings.JWT_SECRET_KEY else 'Ausente (CRÍTICO para Auth)'}")
    print(f"  SYNC_DATABASE_CRUD_URL (Generado): {settings.SYNC_DATABASE_CRUD_URL}")