# app/models/api_client.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON # type: ignore
from sqlalchemy.sql import func # type: ignore
from app.db.session import Base_CRUD 

class ApiClient(Base_CRUD):
    __tablename__ = "api_clients"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    hashed_api_key = Column(String(255), unique=True, nullable=False) 
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    settings = Column(JSON, nullable=True) # Esto es flexible para nuestra nueva estructura de settings
    webchat_ui_config = Column(JSON, nullable=True, comment="Configuración visual para el widget de webchat embebible.")
    is_premium = Column(Boolean, default=False, nullable=False, comment="Indica si el cliente tiene acceso a funcionalidades premium.")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ApiClient(id={self.id}, name='{self.name}', is_active={self.is_active})>"

    # Atributo temporal para la clave en texto plano (NO PERSISTENTE)
    # SQLAlchemy no lo gestionará en la BD, es solo para el objeto en memoria.
    # No es necesario definirlo aquí si solo lo añades dinámicamente en el CRUD.
    # temp_api_key_plain: Optional[str] = None 

    # Atributo temporal para los detalles de los contextos (NO PERSISTENTE)
    # Lo mismo, se puede añadir dinámicamente en el CRUD.
    # transient_allowed_contexts_details: List[Any] = [] # Tipado real sería List[ContextDefinitionModel]