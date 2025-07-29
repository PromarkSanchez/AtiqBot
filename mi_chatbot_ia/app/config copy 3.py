# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List, Any
from dotenv import load_dotenv
import os

# ==========================================================
# ======>      LÍNEA MÁS IMPORTANTE DEL REFACTOR       <======
# ==========================================================
# Se llama a load_dotenv() al principio del módulo.
# Esto asegura que CUALQUIER importación posterior que use os.getenv()
# ya encontrará las variables del archivo .env cargadas en el entorno.
load_dotenv()


class Settings(BaseSettings):
    """
    Clase que centraliza todas las configuraciones de la aplicación.
    Lee variables de entorno desde el archivo .env gracias a `load_dotenv()` 
    y a la configuración de Pydantic.
    """
    
    # --- URLs de Bases de Datos ---
    DATABASE_CRUD_URL: str
    DATABASE_VECTOR_URL: str
    SYNC_DATABASE_CRUD_URL: Optional[str] = None
    SYNC_DATABASE_VECTOR_URL: Optional[str] = None

    # --- Configuración LLM y Embeddings (Ahora más agnóstico) ---
    # [REFACTOR] GEMINI_API_KEY se deja como opcional. Cada modelo en la BD
    # especificará qué variable de entorno usar (ej. OPENAI_API_KEY, etc.)
    # Ya no es una dependencia "global", pero es útil tenerla para validaciones.
    GEMINI_API_KEY: Optional[str] = None
    
    # [REFACTOR] Se elimina el modelo LLM por defecto "en duro".
    # La lógica del chatbot ahora exige que se configure en el ApiClient.
    # DEFAULT_LLM_MODEL_NAME: str = "models/gemini-1.5-flash-latest"  # <-- ELIMINADO
    DEFAULT_LLM_TEMPERATURE: float = 0.7 # Se puede mantener como fallback
    
    MODEL_NAME_SBERT_FOR_EMBEDDING: str = "all-MiniLM-L6-v2"
    
    # --- Configuración General de la Aplicación ---
    LANGCHAIN_VERBOSE: bool = True
    PGVECTOR_CHAT_COLLECTION_NAME: str = "chatbot_knowledge_base_v1"
    CHAT_HISTORY_TABLE_NAME: str = "chat_message_history_v2"
    FERNET_KEY: str # Se hace no opcional para forzar su configuración en .env
    
    # --- Active Directory (Admin Auth) ---
    AD_SERVER_URL: Optional[str] = "ldap://172.17.100.2"
    AD_BASE_DN: Optional[str] = "dc=upch,dc=edu,dc=pe"
    AD_UPN_SUFFIX: Optional[str] = "upch.edu.pe"
    AD_DOMAIN_NT: Optional[str] = "upchnt"
    AD_USERNAME_AD_ATTRIBUTE_TO_STORE: str = "sAMAccountName"
    AD_TIMEOUT_SECONDS: int = 10
    
    # --- JWT (Admin Auth) ---
    JWT_SECRET_KEY: str # No opcional
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8
    JWT_PRE_MFA_TOKEN_EXPIRE_MINUTES: int = 5
    
    # --- MFA (Admin Auth) ---
    MFA_APP_NAME: str = "ChatBotIA"
    
    # --- Configuración Específica del Chatbot y Lógica de Intenciones ---
    DW_CONTEXT_CONFIG_NAME: str = "Esquema Data Warehouse Principal"
    SQL_INTENT_KEYWORDS: List[str] = ["describe la tabla", "columnas de", "esquema de", "total de registros", "promedio de"]
    DW_TABLE_PREFIXES_FOR_INTENT: List[str] = ["AGR_", "DIM_", "FCT_", "FACT_"]
    MAX_RETRIEVED_CHUNKS_RAG: int = 6
    CHAT_HISTORY_WINDOW_SIZE_RAG: int = 6
    CHAT_HISTORY_WINDOW_SIZE_SQL: int = 0

    # ==========================================================
    # ======>     PROMPTS POR DEFECTO / FALLBACK      <======
    # ==========================================================
    # [REFACTOR] Estos prompts ahora sirven como un respaldo (fallback).
    # La lógica principal debería obtener el prompt del "Perfil de Agente Virtual".
    # Por ahora, los mantenemos aquí para que el sistema siga funcionando
    # mientras construimos esa parte de la lógica.
    DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE: str = (
        "Dada una conversación y una pregunta de seguimiento, tu ÚNICA tarea es reformular la pregunta "
        "para que sea una pregunta independiente y completa. **CONCÉNTRATE PRINCIPALMENTE EN LA ÚLTIMA PREGUNTA DEL USUARIO.** "
        "No mezcles temas de preguntas anteriores a menos que sea absolutamente necesario para dar contexto. "
        "Si la última pregunta ya es clara, devuélvela tal cual.\n\n"
        "Historial del Chat:\n{chat_history}\n\n"
        "Pregunta de Seguimiento: {question}\n"
        "Pregunta Independiente y Enfocada:"
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

    # [REFACTOR] Se simplifica el constructor __init__ y las validaciones.
    # El método para generar las URLs síncronas se mantiene.
    def __init__(self, **values: Any):
        super().__init__(**values)
        if self.DATABASE_CRUD_URL and not self.SYNC_DATABASE_CRUD_URL:
            self.SYNC_DATABASE_CRUD_URL = self.DATABASE_CRUD_URL.replace("postgresql+asyncpg", "postgresql")
        if self.DATABASE_VECTOR_URL and not self.SYNC_DATABASE_VECTOR_URL:
            self.SYNC_DATABASE_VECTOR_URL = self.DATABASE_VECTOR_URL.replace("postgresql+asyncpg", "postgresql")
        
        # Las validaciones post-inicialización pueden ser útiles, las dejamos.
        if not self.FERNET_KEY:
            print("ADVERTENCIA CONFIG: FERNET_KEY no está configurado en .env. La encriptación de MFA fallará.")
        if not self.JWT_SECRET_KEY:
            print("ERROR CRÍTICO CONFIG: JWT_SECRET_KEY no está configurado en .env. La autenticación JWT fallará.")
        if not self.AD_SERVER_URL or not self.AD_BASE_DN:
            print("ADVERTENCIA CONFIG: Las credenciales de Active Directory no están completas. La autenticación AD podría fallar.")


# Creamos una única instancia global de la configuración para ser usada en toda la app.
settings = Settings()

# Puedes mantener este bloque para depurar tus configuraciones al ejecutar el archivo directamente.
if __name__ == "__main__":
    print("--- Configuraciones Cargadas desde app/config.py ---")
    print(f"  PROJECT_NAME: {settings.PROJECT_NAME if hasattr(settings, 'PROJECT_NAME') else 'No Definido'}")
    print(f"  DATABASE_CRUD_URL: {'...' + settings.DATABASE_CRUD_URL[-10:] if settings.DATABASE_CRUD_URL else 'No Definido'}")
    print(f"  GEMINI_API_KEY: {'Presente' if settings.GEMINI_API_KEY else 'Ausente (Normal si se usan otros proveedores)'}")
    print(f"  FERNET_KEY: {'Presente' if settings.FERNET_KEY else 'Ausente (CRÍTICO para MFA)'}")
    print(f"  JWT_SECRET_KEY: {'Presente' if settings.JWT_SECRET_KEY else 'Ausente (CRÍTICO para Auth)'}")
    print(f"  SYNC_DATABASE_CRUD_URL (Generado): {settings.SYNC_DATABASE_CRUD_URL}")