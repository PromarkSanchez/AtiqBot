# app/models/db_connection_config.py
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Enum as SAEnum # type: ignore
from sqlalchemy.sql import func # type: ignore
from app.db.session import Base_CRUD # En la BD de CRUDs
import enum # Para el Enum de Python

# Definir los tipos de base de datos soportados como un Enum
class SupportedDBType(str, enum.Enum):
    POSTGRESQL = "POSTGRESQL"
    SQLSERVER = "SQLSERVER"
    MYSQL = "MYSQL"
    ORACLE = "ORACLE"
    # Añade otros según necesites (ej. AWS_RDS_POSTGRES, AWS_RDS_MYSQL)

class DatabaseConnectionConfig(Base_CRUD):
    __tablename__ = "db_connection_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    db_type = Column(SAEnum(SupportedDBType, name="supported_db_type_enum"), nullable=False)
    
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    database_name = Column(String(100), nullable=False)
    username = Column(String(100), nullable=False)
    
    # La contraseña se guarda encriptada
    encrypted_password = Column(String(512), nullable=True) # Suficiente para Fernet
    
    # Para parámetros adicionales específicos del driver (ej. driver para SQL Server, charset para MySQL)
    extra_params = Column(JSON, nullable=True) # Ejemplo: {"driver": "ODBC Driver 17 for SQL Server"}

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<DatabaseConnectionConfig(id={self.id}, name='{self.name}', type='{self.db_type.value}')>"