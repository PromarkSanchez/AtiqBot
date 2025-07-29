# app/models/role.py

from sqlalchemy import Column, Integer, String, Text, DateTime  # type: ignore
from sqlalchemy.orm import relationship                       # type: ignore
from sqlalchemy.sql import func                                 # type: ignore
from app.db.session import Base_CRUD                          # Importa tu Base declarativa

class Role(Base_CRUD):
    __tablename__ = "roles"  # Tabla para roles de administración

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False, index=True, comment="Nombre único del rol (ej. superadmin, context_editor)")
    description = Column(Text, nullable=True, comment="Descripción del rol")

    # Relación para ver qué usuarios (AppUser) tienen este rol
    users = relationship("AppUser", secondary="user_role_association", back_populates="roles")

    # --- NUEVA RELACIÓN AÑADIDA ---
    # Define la relación con AdminRoleMenuPermission.
    # Si un Rol es eliminado, sus permisos de menú asociados también lo serán gracias a la cascada.
    menu_permissions = relationship("AdminRoleMenuPermission", back_populates="role", cascade="all, delete-orphan")
    # -----------------------------
    context_permissions = relationship("RoleContextPermission", back_populates="role", cascade="all, delete-orphan")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    context_permissions = relationship("RoleContextPermission", back_populates="role", cascade="all, delete-orphan") 

    def __repr__(self):
        return f"<Role(id={self.id}, name='{self.name}')>"