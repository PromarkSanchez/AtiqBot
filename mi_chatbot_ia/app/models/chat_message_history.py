# app/models/chat_message_history.py
from sqlalchemy import Column, Integer, String, Text, JSON, DateTime # O el tipo que use Langchain para 'message'
from sqlalchemy.sql import func
from app.db.session import Base_CRUD # Usando la misma Base

class ChatMessageHistoryV2(Base_CRUD):
    __tablename__ = "chat_message_history_v2" # Coincide con el nombre de tabla de Langchain

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), nullable=False, index=True)
    
    # 'message' suele ser JSONB en implementaciones de SQLChatMessageHistory de Langchain.
    # Verifica cómo está realmente definida en tu BD si Langchain ya la creó.
    message_json = Column(JSON, nullable=False, name="message") # 'name' para el nombre real de la columna
    
    # Podrías tener un campo 'type' o 'role'
    # message_type = Column(String(50), nullable=True) 
    
    # A veces incluyen un timestamp
    # created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ChatMessageHistoryV2(session_id='{self.session_id}', id={self.id})>"