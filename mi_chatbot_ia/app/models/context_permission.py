# app/models/context_permission.py

from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

from app.db.session import Base_CRUD

class RoleContextPermission(Base_CRUD):
    __tablename__ = 'role_context_permissions'
    id = Column(Integer, primary_key=True)
    role_id = Column(Integer, ForeignKey('roles.id', ondelete="CASCADE"), nullable=False)
    context_definition_id = Column(Integer, ForeignKey('context_definitions.id', ondelete="CASCADE"), nullable=False)
    role = relationship("Role", back_populates="context_permissions")
    context_definition = relationship("ContextDefinition", back_populates="role_permissions")


