# app/models/user_role_association.py
from sqlalchemy import Column, Integer, ForeignKey, Table 
from app.db.session import Base_CRUD

# == CAMBIO: Renombrar la variable ==
user_role_association = Table( # Ahora se llama 'user_role_association'
    "user_role_association", # Nombre de la tabla física (puede seguir igual)
    Base_CRUD.metadata,
    Column("app_user_id", Integer, ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
)