# app/models/human_agent.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, Table, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base_CRUD # Asumiendo que esta es tu Base declarativa
# No necesitamos importar HumanAgentGroup aquí para la tabla de asociación si usamos string para la clase
# pero lo necesitaremos para los type hints de la relación.

# Tabla de asociación para la relación Muchos-a-Muchos entre HumanAgent y HumanAgentGroup
human_agent_group_association = Table(
    "human_agent_group_assignment_assoc", # Un nombre un poco más descriptivo para la tabla de asociación
    Base_CRUD.metadata,
    Column("human_agent_id", Integer, ForeignKey("human_agents.id", ondelete="CASCADE", name="fk_hag_assoc_human_agent_id"), primary_key=True),
    Column("human_agent_group_id", Integer, ForeignKey("human_agent_groups.id", ondelete="CASCADE", name="fk_hag_assoc_group_id"), primary_key=True),
    comment="Tabla de asociación para asignar agentes humanos a grupos de agentes."
)

class HumanAgent(Base_CRUD):
    __tablename__ = "human_agents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(150), nullable=False, comment="Nombre completo del agente humano.")
    email = Column(String(255), unique=True, index=True, nullable=False, comment="Email del agente, usado para notificaciones o identificación.")
    teams_id = Column(String(255), nullable=True, unique=True, index=True, comment="ID de usuario de Microsoft Teams (si se usa para notificaciones/handoff).")
    
    is_active = Column(Boolean, default=True, nullable=False, comment="Indica si el agente está actualmente activo en el sistema (no necesariamente 'disponible' en este instante).")
    # 'is_available' podría ser un campo más dinámico o derivado. Lo mantendremos simple por ahora.
    # La disponibilidad real se manejaría con el calendario o la configuración del agente.
    
    availability_config_json = Column(JSON, nullable=True, 
                                      comment="Configuración JSON para horarios de trabajo, días libres, o enlace/ID a sistema de calendario externo.")
    # Ejemplo: {"work_hours": {"monday": "09:00-17:00", ...}, "time_zone": "America/Lima", "calendar_id": "agente1@example.com"}

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relación Muchos-a-Muchos con HumanAgentGroup
    agent_groups = relationship(
        "HumanAgentGroup", # Nombre de la CLASE como string
        secondary=human_agent_group_association,
        back_populates="agents", # 'agents' será el atributo en HumanAgentGroupModel
        lazy="selectin" # Cargar los grupos ansiosamente cuando se carga un HumanAgent
    )

    def __repr__(self):
        return f"<HumanAgent(id={self.id}, name='{self.full_name}', email='{self.email}')>"

class HumanAgentGroup(Base_CRUD):
    __tablename__ = "human_agent_groups"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, 
                  comment="Nombre del grupo/equipo de agentes humanos (ej: 'Soporte Técnico Nivel 1', 'Expertos en Admisiones').")
    description = Column(Text, nullable=True, comment="Descripción del propósito del grupo.")
    is_active = Column(Boolean, default=True, nullable=False, comment="Si el grupo está activo para recibir derivaciones.")
    
    # Podría tener un campo JSON para 'routing_config' (ej. {"method": "round_robin"})
    routing_config_json = Column(JSON, nullable=True, comment="Configuración para el enrutamiento de chats dentro del grupo.")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relación Muchos-a-Muchos con HumanAgent
    agents = relationship(
        "HumanAgent", # Nombre de la CLASE como string
        secondary=human_agent_group_association,
        back_populates="agent_groups", # 'agent_groups' será el atributo en HumanAgentModel
        lazy="selectin" # Cargar los agentes ansiosamente cuando se carga un HumanAgentGroup
    )
    
    # Relación inversa (si los ApiClients apuntan a este)
    # api_clients_using_for_handoff (definido por backref en ApiClientModel, si es que un ApiClient solo apunta a UN grupo)
    # O si ApiClientModel tiene un campo human_handoff_agent_group_id, no se necesita backref aquí.

    def __repr__(self):
        return f"<HumanAgentGroup(id={self.id}, name='{self.name}')>"