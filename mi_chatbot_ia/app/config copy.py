# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List, Any, Dict 
from datetime import timedelta
import os

class Settings(BaseSettings):
    # --- URLs BD ---
    DATABASE_CRUD_URL: str 
    DATABASE_VECTOR_URL: str 
    SYNC_DATABASE_CRUD_URL: Optional[str] = None 
    SYNC_DATABASE_VECTOR_URL: Optional[str] = None
    
    # --- LLM y App General ---
    GEMINI_API_KEY: Optional[str] = None
    DEFAULT_LLM_MODEL_NAME: str  = "models/gemini-1.5-flash-latest"
    DEFAULT_LLM_TEMPERATURE: float = 0.7
    LANGCHAIN_VERBOSE: bool = True # PUESTO A TRUE para logs

    # --- NUEVOS Y LOS QUE ESTABAN EN CHAT_API_ENDPOINTS Y NECESITAN ESTAR AQUÍ ---
    MODEL_NAME_SBERT_FOR_EMBEDDING: str = "all-MiniLM-L6-v2"       # <--- Asegúrate que esté
    PGVECTOR_CHAT_COLLECTION_NAME: str = "chatbot_knowledge_base_v1" # <--- Asegúrate que esté
    CHAT_HISTORY_TABLE_NAME: str = "chat_message_history_v2"      # <--- ¡EL QUE CAUSÓ EL ERROR AHORA! Asegúrate que esté
    # --------------------------------------------------------------------------

    # --- Fernet (Encriptación) ---
    FERNET_KEY: Optional[str] = None # ¡DEBE ESTAR EN .env!

    # --- Active Directory (Admin Auth) ---
    AD_SERVER_URL: Optional[str] = "ldap://172.17.100.2" 
    AD_BASE_DN: Optional[str] = "dc=upch,dc=edu,dc=pe"   
    AD_UPN_SUFFIX: Optional[str] = "upch.edu.pe"          
    AD_DOMAIN_NT: Optional[str] = "upchnt"                
    AD_USERNAME_AD_ATTRIBUTE_TO_STORE: str = "sAMAccountName" 
    AD_TIMEOUT_SECONDS: int = 10 

    # --- JWT (Admin Auth) ---
    JWT_SECRET_KEY: str # ¡DEBE ESTAR EN .env!
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8 
    JWT_PRE_MFA_TOKEN_EXPIRE_MINUTES: int = 5    

    # --- MFA (Admin Auth) ---
    MFA_APP_NAME: str = "ChatBotIA" 
    
    # --- CONFIGURACIONES DEL CHATBOT (ya las tenías, verificar que todo lo que usa chat_api_endpoints esté) ---
    DW_CONTEXT_CONFIG_NAME: str = "Esquema Data Warehouse Principal"
    SQL_INTENT_KEYWORDS: List[str] = [
        "cuantos", "total", "lista de", "promedio", "datos de", "informacion de tabla",
        "describe la tabla", "cantidad de", "quienes son", "mostrar", "listar"
    ]
    DW_TABLE_PREFIXES_FOR_INTENT: List[str] = ["AGR_", "DIM_", "FCT_", "FACT_"]
    MAX_RETRIEVED_CHUNKS_RAG: int = 3
    CHAT_HISTORY_WINDOW_SIZE_RAG: int = 6 
    CHAT_HISTORY_WINDOW_SIZE_SQL: int = 0 

    DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE: str = (
        "Dada la siguiente conversación y una pregunta de seguimiento, reformula la pregunta de "
        "seguimiento para que sea una pregunta independiente, en su idioma original.\n"
        "Si la pregunta ya es independiente, devuélvela tal cual.\n\n"
        "Historial de Chat:\n{chat_history}\n\n"
        "Pregunta de Seguimiento: {question}\n"
        "Pregunta Independiente:"
    )
  
    DEFAULT_RAG_DOCS_QA_TEMPLATE: str = (
        "Eres un asistente conversacional útil, amigable y que recuerda interacciones previas.\n" 
        "Tu tarea principal es responder la PREGUNTA del usuario de la manera más natural posible.\n"
        "Tienes dos fuentes de información: el HISTORIAL DE CHAT y el CONTEXTO EXTRAÍDO de documentos.\n\n"
        "INSTRUCCIONES IMPORTANTES:\n"
        "1. Revisa primero el HISTORIAL DE CHAT. Si la PREGUNTA del usuario es sobre información que él/ella ya te ha proporcionado anteriormente (como su nombre, preferencias, detalles de una conversación previa, etc.), y esa información está CLARAMENTE en el HISTORIAL DE CHAT, responde directamente basándote en esa información como si la recordaras naturalmente. **No es necesario que menciones 'el historial de chat' en tu respuesta al usuario.**\n" 
        "2. Si la PREGUNTA no puede ser respondida solo con el HISTORIAL DE CHAT (o no es una pregunta personal), entonces utiliza el CONTEXTO EXTRAÍDO para encontrar la respuesta. Si encuentras información relevante en el CONTEXTO EXTRAÍDO, úsala.\n"
        "3. Si la PREGUNTA requiere información del CONTEXTO EXTRAÍDO y el contexto no contiene la respuesta, indica amablemente que no tienes esa información en los documentos disponibles.\n"
        "4. Si la PREGUNTA NO puede ser respondida ni por la información que recuerdas del HISTORIAL ni por el CONTEXTO EXTRAÍDO, informa que no tienes la información necesaria en este momento.\n"
        "5. NO inventes información. Sé preciso.\n"
        "6. Responde en español y de forma conversacional.\n\n"
        "HISTORIAL DE CHAT (interacciones previas que te ayudan a recordar):\n"
        "{chat_history}\n\n"
        "CONTEXTO EXTRAÍDO (documentos relevantes para preguntas que no son personales o que el historial no cubre):\n"
        "{context}\n\n"
        "PREGUNTA (la pregunta actual del usuario, ya independiente del historial):\n"
        "{question}\n\n"
        "Respuesta Natural y Amigable:"
    )
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

    def __init__(self, **values: Any):
        super().__init__(**values)
        
        if self.DATABASE_CRUD_URL and self.SYNC_DATABASE_CRUD_URL is None:
            self.SYNC_DATABASE_CRUD_URL = self.DATABASE_CRUD_URL.replace("postgresql+asyncpg", "postgresql")
        if self.DATABASE_VECTOR_URL and self.SYNC_DATABASE_VECTOR_URL is None:
            self.SYNC_DATABASE_VECTOR_URL = self.DATABASE_VECTOR_URL.replace("postgresql+asyncpg", "postgresql")
        
        if not hasattr(self, 'FERNET_KEY') or not self.FERNET_KEY:
             print("ADVERTENCIA CONFIG: FERNET_KEY no configurado o vacío. Encriptación MFA fallará.")
        if not hasattr(self, 'JWT_SECRET_KEY') or not self.JWT_SECRET_KEY:
            print("ERROR CRÍTICO CONFIG: JWT_SECRET_KEY no configurado o vacío. JWTs fallarán.")
            # Considera no lanzar ValueError aquí si quieres que la app intente arrancar para otros endpoints,
            # pero el print es suficiente para alertar.
            # raise ValueError("JWT_SECRET_KEY es requerida y debe tener un valor seguro en .env.")
        if not self.AD_SERVER_URL or not self.AD_BASE_DN:
            print("ADVERTENCIA CONFIG: AD_SERVER_URL o AD_BASE_DN no configurados. Autenticación AD fallará.")
        if not self.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE or not self.DEFAULT_RAG_DOCS_QA_TEMPLATE:
            print("ADVERTENCIA CONFIG: Una o más plantillas de prompt por defecto están vacías.")

settings = Settings()

# El bloque if __name__ == "__main__" para imprimir configuraciones está bien para debug local.
# (Lo omito aquí por brevedad, pero puedes mantener el tuyo).
if __name__ == "__main__":
    print("Configuraciones Cargadas:")
    print(f"  DATABASE_CRUD_URL: {settings.DATABASE_CRUD_URL}")
    print(f"  SYNC_DATABASE_CRUD_URL: {settings.SYNC_DATABASE_CRUD_URL}")
    print(f"  DATABASE_VECTOR_URL: {settings.DATABASE_VECTOR_URL}")
    print(f"  SYNC_DATABASE_VECTOR_URL: {settings.SYNC_DATABASE_VECTOR_URL}")
    print(f"  GEMINI_API_KEY: {'Presente' if settings.GEMINI_API_KEY else 'Ausente'}")
    print(f"  DEFAULT_LLM_MODEL_NAME: {settings.DEFAULT_LLM_MODEL_NAME}")
    print(f"  DEFAULT_LLM_TEMPERATURE: {settings.DEFAULT_LLM_TEMPERATURE}")
    print(f"  FERNET_KEY: {'Presente' if settings.FERNET_KEY else 'Ausente'}")
    print(f"  LANGCHAIN_VERBOSE: {settings.LANGCHAIN_VERBOSE}") # <-- Verifica que aparezca aquí
    print(f"AD_SERVER_URL: {settings.AD_SERVER_URL}")
    print(f"FERNET_KEY: {'Set' if settings.FERNET_KEY else 'Not Set'}")
    print(f"JWT_SECRET_KEY: {'Set' if settings.JWT_SECRET_KEY else 'Not Set (CRITICAL ERROR IF RUNNING APP)'}")
