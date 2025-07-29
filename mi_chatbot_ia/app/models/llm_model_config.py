# app/models/llm_model_config.py

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, Enum as SAEnum, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base_CRUD
import enum
 # --- ENUMS (Sin cambios) ---
class LLMProviderType(str, enum.Enum):
    GOOGLE = "GOOGLE"
    OPENAI = "OPENAI"
    AZURE_OPENAI = "AZURE_OPENAI"
    ANTHROPIC = "ANTHROPIC"
    HUGGINGFACE_LOCAL = "HUGGINGFACE_LOCAL"
    OLLAMA = "OLLAMA"
    CUSTOM = "CUSTOM"
    BEDROCK = "BEDROCK"
    
class LLMModelType(str, enum.Enum):
    CHAT_COMPLETION = "CHAT_COMPLETION"
    TEXT_GENERATION = "TEXT_GENERATION"
    EMBEDDING = "EMBEDDING"

# --- Modelo SQLAlchemy (Refactorizado) ---
class LLMModelConfig(Base_CRUD):
    __tablename__ = "llm_model_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    model_identifier = Column(String(255), unique=True, nullable=False, index=True,
                              comment="Identificador único del modelo como se usa en la API del proveedor (ej. 'gemini-1.5-pro-latest', 'gpt-4-turbo').")
    
    display_name = Column(String(150), nullable=False, 
                          comment="Nombre amigable para mostrar en la UI del panel (ej. 'Gemini 1.5 Pro (Google)').")
    
    provider = Column(SAEnum(LLMProviderType, name="llm_provider_type_enum", create_type=True), nullable=False, index=True,
                      comment="Proveedor del modelo LLM (Google, OpenAI, Azure, etc.).")
    
    model_type = Column(SAEnum(LLMModelType, name="llm_model_type_enum", create_type=True), nullable=False, default=LLMModelType.CHAT_COMPLETION,
                        comment="Tipo principal de tarea para la que se usa este modelo.")

    is_active = Column(Boolean, default=True, nullable=False,
                       comment="Indica si este modelo está activo y disponible para ser usado.")
    
    # ==========================================================
    # ============>       CAMBIO DE ARQUITECTURA       <============
    # ==========================================================
    # ELIMINADO: api_key_env_var = Column(String(100), nullable=True)
    api_key_encrypted = Column(Text, nullable=True, 
                               comment="La API Key, encriptada con Fernet usando la clave de entorno FERNET_KEY.")
    # ==========================================================
    
    base_url = Column(String(512), nullable=True,
                      comment="URL base para el endpoint del modelo. Útil para modelos auto-hospedados, proxies, o Azure.")

    default_temperature = Column(Float, nullable=True, default=0.7,
                                 comment="Temperatura por defecto para las respuestas de este modelo (0.0 a 2.0).")
    
    default_max_tokens = Column(Integer, nullable=True, default=2048,
                                comment="Máximo de tokens por defecto que puede generar este modelo.")
    
    supports_system_prompt = Column(Boolean, default=True, nullable=False,
                                    comment="Indica si este modelo maneja bien un 'system prompt' separado.")

    config_json = Column(JSON, nullable=True, 
                         comment="JSON para parámetros de configuración adicionales específicos del proveedor (ej. para Azure).")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


    def __repr__(self):
        return f"<LLMModelConfig(id={self.id}, display_name='{self.display_name}', provider='{self.provider.value}')>"