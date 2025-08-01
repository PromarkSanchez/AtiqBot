# app/models/virtual_agent_profile.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base_CRUD
from sqlalchemy.dialects.postgresql import JSONB

# No necesitamos importar LLMModelConfig aquí si la relación se define con string y luego se resuelve,
# pero importarlo es más explícito para la FK.
# from .llm_model_config import LLMModelConfig # Descomentar si se usa el tipo en relationship

class VirtualAgentProfile(Base_CRUD):
    __tablename__ = "virtual_agent_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(150), unique=True, nullable=False, index=True,
                  comment="Nombre único para este perfil de agente virtual (ej. 'Asesor Académico Proactivo').")
    
    description = Column(Text, nullable=True,
                         comment="Descripción para uso interno del admin sobre el propósito de este perfil.")
    
    user_provided_goal_description = Column(Text, nullable=True,
                                             comment="Descripción breve del objetivo/rol que el admin provee, usada como base para la generación asistida de prompts.")
    
    # === Prompts para las etapas del flujo de conversación (ETAPA 1, ETAPA 2, ETAPA 3) ===
    system_prompt = Column(Text, nullable=False, comment="El prompt principal para resolver consultas (ETAPA 3).")
    
    greeting_prompt = Column(Text, nullable=True, comment="Prompt para la ETAPA 1: Saludo inicial.")
    
    name_confirmation_prompt = Column(Text, nullable=True, comment="Prompt para la ETAPA 2: Confirmación de nombre.")
    character_sheet_json = Column(JSONB, nullable=True)


    llm_model_config_id = Column(Integer, ForeignKey("llm_model_configs.id", name="fk_vap_llm_model_config_id"), nullable=False)
    llm_model_config = relationship("LLMModelConfig", backref="virtual_agent_profiles") # Nombre de clase como string

    temperature_override = Column(Float, nullable=True, 
                                  comment="Si se especifica, sobrescribe la temperatura del LLMModelConfig asociado.")
    max_tokens_override = Column(Integer, nullable=True, 
                                 comment="Si se especifica, sobrescribe el max_tokens del LLMModelConfig asociado.")
    
    is_active = Column(Boolean, default=True, nullable=False,
                       comment="Indica si este perfil de agente está activo y puede ser seleccionado/usado.")
    default_user_role = Column(String(100), nullable=False, default="Usuario")
    fallback_prompt = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relación inversa (si los Contexts o ApiClients apuntan a este)
    # contexts_using_as_default (definido por backref en ContextDefinition)
    # api_clients_overriding_with (definido por backref en ApiClient)

    def __repr__(self):
        return f"<VirtualAgentProfile(id={self.id}, name='{self.name}')>"