# app/models/app_user.py
import enum  # <-- AÑADE ESTE IMPORT NATIVO

from sqlalchemy import  Column, Integer, String, Boolean, DateTime, Enum as SQLAlchemyEnum # type: ignore 
from sqlalchemy.orm import relationship # type: ignore 
from sqlalchemy.sql import func # type: ignore 
from app.db.session import Base_CRUD # Importa tu Base declarativa
from app.models.role import Role # Importar Role para la relación
from .user_role_association import user_role_association # Si se llama así la tabla de asociación

# Define la clase Enum que se usará en la columna `auth_method`.
class AuthMethod(str, enum.Enum):
    LOCAL = "local"
    AD = "ad"
# -----------------------------
class AppUser(Base_CRUD):
    __tablename__ = "app_user" # Usuarios de la aplicación/administradores

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Identificador único del usuario en Active Directory (será el DNI)
    username_ad = Column(String(255), unique=True, index=True, nullable=False, comment="DNI del usuario, usado como identificador de AD") 
    
    email = Column(String(255), unique=True, index=True, nullable=True, comment="Email, idealmente obtenido de AD")
    full_name = Column(String(255), nullable=True, comment="Nombre completo, idealmente obtenido de AD")
    
    # Control de activación local, para deshabilitar un usuario admin sin afectarlo en AD
    is_active_local = Column(Boolean, default=True, nullable=False, comment="Si el usuario está activo en este sistema")
    
    # --- CAMPOS NUEVOS PARA LOGIN GENÉRICO ---
    hashed_password = Column(String(255), nullable=True, comment="Contraseña hasheada para usuarios con auth_method 'local'")
    auth_method = Column(SQLAlchemyEnum(AuthMethod, name="auth_method_enum", create_type=False,values_callable=lambda obj: [e.value for e in obj]), 
                        default=AuthMethod.AD.value, # Pequeño ajuste aquí también
                        nullable=False,
                        comment="Método de autenticación a usar: 'local' o 'ad'")
    # ------------------------------------------

    # --- Campos para MFA TOTP ---
    mfa_secret_encrypted = Column(String(512), nullable=True, comment="Secreto TOTP encriptado (con Fernet)") 
    mfa_enabled = Column(Boolean, default=False, nullable=False, comment="Indica si MFA está habilitado para este usuario")
    
    # Relación con Roles
    roles = relationship("Role", secondary=user_role_association, back_populates="users")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<AppUser(id={self.id}, username_ad='{self.username_ad}', is_active_local={self.is_active_local})>"