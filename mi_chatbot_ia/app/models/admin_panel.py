# app/models/admin_panel.py

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime # type: ignore
from sqlalchemy.orm import relationship # type: ignore
from sqlalchemy.sql import func # type: ignore
from app.db.session import Base_CRUD # Importa tu Base declarativa

class AdminPanelMenu(Base_CRUD):
    __tablename__ = 'admin_panel_menus'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, index=True, nullable=False, comment="Nombre del menú para la UI, ej. 'Gestión de Contextos'")
    frontend_route = Column(String(255), unique=True, nullable=False, comment="Ruta en el frontend, ej. '/admin/contexts'")
    icon_name = Column(String(100), nullable=True, comment="Nombre del icono para que el frontend lo interprete, ej. 'BookOpenIcon'")
    parent_id = Column(Integer, ForeignKey('admin_panel_menus.id'), nullable=True, comment="Para anidar menús, si es necesario")
    display_order = Column(Integer, default=100, comment="Orden para mostrar en la UI (menor número primero)")

    permissions = relationship("AdminRoleMenuPermission", back_populates="menu")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<AdminPanelMenu(id={self.id}, name='{self.name}')>"

class AdminRoleMenuPermission(Base_CRUD):
    __tablename__ = 'admin_role_menu_permissions'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey('roles.id', ondelete='CASCADE'), nullable=False)
    menu_id = Column(Integer, ForeignKey('admin_panel_menus.id', ondelete='CASCADE'), nullable=False)
    
    can_view = Column(Boolean, default=True, nullable=False)
    
    # Relaciones para acceder a los objetos Role y AdminPanelMenu
    role = relationship("Role", back_populates="menu_permissions")
    menu = relationship("AdminPanelMenu", back_populates="permissions")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<AdminRoleMenuPermission(role_id={self.role_id}, menu_id={self.menu_id})>"