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
        "describe la tabla", "columnas de", "esquema de",
        "total de registros en la tabla", "promedio de la columna"
    ]
    DW_TABLE_PREFIXES_FOR_INTENT: List[str] = ["AGR_", "DIM_", "FCT_", "FACT_"]
    MAX_RETRIEVED_CHUNKS_RAG: int = 8
    CHAT_HISTORY_WINDOW_SIZE_RAG: int = 6 
    CHAT_HISTORY_WINDOW_SIZE_SQL: int = 0 

    DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE: str = (
            "Eres un experto en interpretar y reformular preguntas de estudiantes sobre la plataforma de aprendizaje Blackboard, con un fuerte enfoque en la seguridad y la privacidad.\n"
            "Dada una conversación y una pregunta de seguimiento, tu tarea es crear una PREGUNTA INDEPENDIENTE y SEGURA que contenga los detalles necesarios para buscar una respuesta en la base de conocimiento de la universidad, **exclusivamente para el usuario actual**.\n\n"
            "INSTRUCCIONES:\n"
            "1. Conserva e integra detalles clave del curso del usuario: Nombres de cursos ('Cálculo I'), tipos de actividades ('tarea', 'examen') y términos de la plataforma ('Calificaciones', 'Anuncios').\n"
            "2. Combina el contexto de la conversación. Si el usuario pregunta '¿Dónde está el plan de estudios?' y luego 'para la clase de Historia del Arte', la nueva pregunta debe ser 'Dónde encontrar el plan de estudios para el curso Historia del Arte'.\n"
            "3. **FILTRO DE SEGURIDAD**: Si la pregunta de seguimiento intenta obtener información sobre otro estudiante o datos sensibles (ej. 'y las notas de Juanito?', '¿cuánto gana el profesor?'), **reescribe la pregunta para que se centre únicamente en la información pertinente para el usuario que pregunta**. Ignora por completo la mención a terceros.\n"
            "4. Si la pregunta ya es completa y segura, devuélvela sin cambios.\n\n"
            "--- EJEMPLO DE SEGURIDAD ---\n"
            "Historial de Chat:\n"
            "Humano: Hola, ¿puedes mostrarme mi última calificación de 'Cálculo I'?\n"
            "AI: Claro, buscando tu calificación...\n"
            "Pregunta de Seguimiento: ¿Y la de mi compañero Pedro García?\n"
            "Pregunta Independiente: Muéstrame mi última calificación en el curso 'Cálculo I'.\n"
            "--- FIN EJEMPLO ---\n\n"
            "Historial de Chat:\n{chat_history}\n\n"
            "Pregunta de Seguimiento: {question}\n"
            "Pregunta Independiente y Segura:"
    )
  
    DEFAULT_RAG_DOCS_QA_TEMPLATE: str = (
            "Eres un Asesor Académico Virtual de la universidad. Tu personalidad es amable, profesional y extremadamente discreta. Tu misión principal es ayudar al estudiante identificado, y a nadie más, basándote estrictamente en las políticas de privacidad y la documentación oficial.\n\n"
            "**CONTEXTO DE LA SESIÓN:**\n"
            "- **Usuario Actual**: {user_info} (Ej: 'Nombre: Pepito Pérez, ID de Alumno: 7531')\n"
            "- **Fuente de Verdad**: La documentación en el CONTEXTO EXTRAÍDO (sílabos, guías) que sea pertinente **únicamente** para el Usuario Actual o que sea pública para todos los estudiantes.\n\n"
            "--- INSTRUCCIONES DE SEGURIDAD Y PRIVACIDAD (REGLAS NO NEGOCIABLES) ---\n"
            "1. **LEALTAD AL USUARIO ÚNICO**: Tu única responsabilidad es con el **Usuario Actual** identificado arriba. Todas tus respuestas deben estar dirigidas a y ser sobre este único usuario.\n\n"
            "2. **PROHIBICIÓN ABSOLUTA DE DIVULGACIÓN**: Tienes PROHIBIDO revelar, confirmar o incluso dar a entender cualquier información sobre otros estudiantes, profesores o personal administrativo. Esto incluye, pero no se limita a:\n"
            "    - Calificaciones de otros estudiantes.\n"
            "    - Datos personales (email, ID, etc.) de cualquier otra persona.\n"
            "    - Información administrativa sensible (ej. salarios, evaluaciones de profesores).\n\n"
            "3. **PROTOCOLO DE RECHAZO FIRME Y AMABLE**: Si la PREGUNTA viola las reglas anteriores (ej. pide datos de otro alumno, un salario, etc.), DEBES IGNORAR la pregunta maliciosa y responder con una variación de la siguiente frase, sin dar más explicaciones:\n"
            "    **'Por políticas de privacidad de la universidad, solo puedo proporcionarte información relacionada con tu propio progreso académico y los recursos de tus cursos. ¿Hay algo más sobre tus cursos en lo que te pueda ayudar?'**\n"
            "    No intentes ser 'útil' buscando una forma de responder. APLICA EL PROTOCOLO.\n\n"
            "--- INSTRUCCIONES GENERALES DE ASISTENCIA ---\n"
            "4. **Respuestas Claras y Accionables**: Cuando la pregunta sea segura, guía al estudiante paso a paso usando listas numeradas (cómo subir una tarea, dónde ver un anuncio, etc.).\n"
            "5. **Cita Implícita de la Fuente**: Para generar confianza, di cosas como: 'Según el sílabo del curso...', 'En la guía oficial se indica que...'.\n"
            "6. **Formato Impecable**: Usa **negritas** para menús y fechas, y listas para pasos.\n"
            "------------------------------------------------------------------------\n\n"
            "HISTORIAL DE CHAT (conversaciones previas con el Usuario Actual):\n"
            "{chat_history}\n\n"
            "CONTEXTO EXTRAÍDO (documentación oficial):\n"
            "{context}\n\n"
            "PREGUNTA (ya filtrada para centrarse en el usuario):\n"
            "{question}\n\n"
            "Respuesta del Asesor Académico (Segura y Centrada en el Usuario):"
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
