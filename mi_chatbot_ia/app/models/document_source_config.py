# app/models/document_source_config.py
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, Enum as SAEnum

from sqlalchemy.sql import func # type: ignore
from app.db.session import Base_CRUD # En la BD de CRUDs
import enum

class SupportedDocSourceType(str, enum.Enum):
    LOCAL_FOLDER = "LOCAL_FOLDER"
    S3_BUCKET = "S3_BUCKET"
    AZURE_BLOB = "AZURE_BLOB"
    WEB_URL_SINGLE = "WEB_URL_SINGLE" # Para una única página web
    # WEB_SCRAPE_SITE = "WEB_SCRAPE_SITE" # Para scrapear un sitio entero (más complejo)
    # Podríamos añadir más, como GOOGLE_DRIVE, NOTION, etc.

class DocumentSourceConfig(Base_CRUD):
    __tablename__ = "document_source_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    source_type = Column(SAEnum(SupportedDocSourceType, name="supported_doc_source_type_enum"), nullable=False)
    
    # path_or_config: almacena la información específica para el source_type
    # - LOCAL_FOLDER: ruta absoluta a la carpeta en el servidor.
    # - S3_BUCKET: {"bucket_name": "nombre-del-bucket", "prefix": "ruta/dentro/del/bucket/"}
    # - AZURE_BLOB: {"container_name": "nombre-contenedor", "connection_string_env_var": "AZURE_STORAGE_CONNECTION_STRING_VARNAME", "prefix": "ruta/"}
    # - WEB_URL_SINGLE: la URL de la página.
    path_or_config = Column(JSON, nullable=False)
    
    # credentials_info_encrypted: para claves S3, connection strings de Azure, etc.
    # Estas TAMBIÉN se encriptarán con Fernet.
    credentials_info_encrypted = Column(Text, nullable=True) # JSON encriptado
    is_active = Column(Boolean, default=True, nullable=False, server_default='true',
    comment="Controla si esta fuente de datos está activa globalmente. Si es False, se ignora en todas las ingestas y búsquedas.")
    # Opcional: Configuración para la frecuencia de re-ingesta/sincronización
    sync_frequency_cron = Column(String(50), nullable=True) # Ej. "0 2 * * *" (todos los días a las 2 AM)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    
    def __repr__(self):
        return f"<DocumentSourceConfig(id={self.id}, name='{self.name}', type='{self.source_type.value}')>"