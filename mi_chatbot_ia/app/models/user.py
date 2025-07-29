# app/models/user.py
from sqlalchemy import Column, String, Integer, Boolean # type: ignore
from sqlalchemy.orm import relationship # type: ignore

 
from app.db.session import Base_CRUD # NUEVO

class User(Base_CRUD):
    __tablename__ = "users" # Nombre de la tabla en la base de datos

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    dni = Column(String(20), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True) # Opcional
    full_name = Column(String(100), nullable=True) # Opcional
    
    # Para la simulación inicial de roles, podríamos añadir un campo de rol aquí.
    # Más adelante, esto podría ser una tabla separada (`roles`) y una tabla de unión (`user_roles`).
    role = Column(String(50), default="user", nullable=False) # Ej: "user", "admin", "editor"
    
    is_active = Column(Boolean, default=True)
    # Podríamos añadir más campos como hashed_password, created_at, updated_at etc.

    # Ejemplo de relación si tuviéramos una tabla de Logs asociada al usuario:
    # logs = relationship("LogEntry", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, dni='{self.dni}', role='{self.role}')>"

# Podrías definir otros modelos aquí (ej. Role, Permission) o en archivos separados.