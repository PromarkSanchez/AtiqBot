# app/models/interaction_log.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON # type: ignore
from sqlalchemy.sql import func # type: ignore
from sqlalchemy.orm import relationship # type: ignore

from app.db.session import Base_CRUD # Usamos la Base para la BD de CRUDs

class InteractionLog(Base_CRUD):
    __tablename__ = "interaction_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # ¿Quién hizo la petición?
    user_dni = Column(String(100), index=True, nullable=True) # DNI del usuario final, si aplica
    # Podríamos añadir una FK a la tabla 'users' si siempre esperamos un usuario registrado.
    # user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # user = relationship("User")

    # ¿A través de qué aplicación cliente vino la petición? (del API Key)
    api_client_name = Column(String(100), nullable=True) # Nombre del cliente API que hizo la llamada
    # api_client_id = Column(Integer, ForeignKey("api_clients.id"), nullable=True) # Si tuviéramos la tabla api_clients
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    user_message = Column(Text, nullable=False)
    
    # Información del RAG
    retrieved_context_summary = Column(Text, nullable=True) # Resumen o IDs de chunks recuperados
    # retrieved_chunk_ids = Column(JSON, nullable=True) # Podría ser una lista de IDs [1, 5, 12]

    full_prompt_to_llm = Column(Text, nullable=True) # El prompt completo enviado al LLM
    
    llm_model_used = Column(String(100), nullable=True) # Ej. 'models/gemini-1.5-flash-latest'
    bot_response = Column(Text, nullable=True)
    
    # Métricas / Errores
    response_time_ms = Column(Integer, nullable=True) # Tiempo de respuesta en milisegundos
    error_message = Column(Text, nullable=True) # Si hubo algún error en el procesamiento
    
    intent = Column(String(100), nullable=True, index=True) # <--- NUEVA COLUMNA para el tipo de query
    metadata_details_json = Column(JSON, nullable=True, name="metadata_details")

    # Feedback (para futuro)
    # feedback_score = Column(Integer, nullable=True) # Ej. 1 para like, -1 para dislike
    # feedback_comment = Column(Text, nullable=True)

    def __repr__(self):
        return f"<InteractionLog(id={self.id}, user_dni='{self.user_dni}', timestamp='{self.timestamp}')>"