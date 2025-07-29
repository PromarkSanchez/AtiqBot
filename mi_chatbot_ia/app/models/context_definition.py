# app/models/context_definition.py
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, Table, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base_CRUD
import enum

# Importar los modelos referenciados en las relaciones
from app.models.document_source_config import DocumentSourceConfig
from app.models.db_connection_config import DatabaseConnectionConfig
from app.models.llm_model_config import LLMModelConfig # == NUEVO ==
from app.models.virtual_agent_profile import VirtualAgentProfile # == NUEVO ==

# Enum para el tipo principal del contexto (SIN CAMBIOS, ya lo tenías)
class ContextMainType(str, enum.Enum):
    DOCUMENTAL = "DOCUMENTAL"
    DATABASE_QUERY = "DATABASE_QUERY"
    IMAGE_ANALYSIS = "IMAGE_ANALYSIS" # Si decides añadir este tipo

# Tabla de asociación para DocumentSourceConfig (SIN CAMBIOS)
context_document_source_association = Table(
    "context_document_source_assoc", Base_CRUD.metadata,
    Column("context_definition_id", Integer, ForeignKey("context_definitions.id", ondelete="CASCADE", name="fk_cdsa_context_id"), primary_key=True),
    Column("document_source_config_id", Integer, ForeignKey("document_source_configs.id", ondelete="CASCADE", name="fk_cdsa_docsource_id"), primary_key=True),
)

class ContextDefinition(Base_CRUD):
    __tablename__ = "context_definitions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(150), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    is_public = Column(Boolean, default=True, nullable=False, 
                    comment="Si es True, este contexto es accesible para sesiones públicas/no autenticadas.")
    main_type = Column(SAEnum(ContextMainType, name="context_main_type_enum_v2", create_type=True), nullable=False) # create_type=True si el enum es nuevo o cambió
    
    processing_config = Column(JSON, nullable=True, comment="Configuración estructurada (JSON) específica del main_type.")
    
    # === CAMBIOS/NUEVOS CAMPOS DE RELACIÓN ===
    default_llm_model_config_id = Column(Integer, ForeignKey("llm_model_configs.id", name="fk_context_def_default_llm_id"), nullable=True)
    default_llm_model_config = relationship(
        "LLMModelConfig", 
        foreign_keys=[default_llm_model_config_id], 
        backref="contexts_using_as_default", # Un contexto usa un LLM como default
        lazy="selectin"
    )

    virtual_agent_profile_id = Column(Integer, ForeignKey("virtual_agent_profiles.id", name="fk_context_def_vap_id"), nullable=True)
    virtual_agent_profile = relationship(
        "VirtualAgentProfile", 
        foreign_keys=[virtual_agent_profile_id],
        backref="contexts_using_as_default", # Un contexto usa un VAP como default
        lazy="selectin"
    )

    # == CAMBIO: Para main_type='DATABASE_QUERY', usamos una FK directa a DBConnectionConfig ==
    # Este campo solo será relevante/poblado si main_type es DATABASE_QUERY.
    # La lógica de negocio/validación asegurará esto.
    db_connection_config_id = Column(Integer, ForeignKey("db_connection_configs.id", name="fk_context_def_db_conn_id"), nullable=True,
                                    comment="FK a db_connection_configs, usado si main_type es DATABASE_QUERY (una única conexión).")
    db_connection_config = relationship( # Relación Uno-a-Uno (o Muchos-a-Uno) desde Contexto a DBConnection
        "DatabaseConnectionConfig", 
        foreign_keys=[db_connection_config_id],
        backref="database_query_contexts", # Un DBConnectionConfig puede ser usado por varios contextos de tipo DATABASE_QUERY
        lazy="selectin"
    )
    # La relación muchos-a-muchos 'db_connections' anterior (con tabla de asociación) 
    # YA NO se usaría para main_type='DATABASE_QUERY' si adoptamos la FK directa.
    # Si otros tipos de contexto SÍ necesitan múltiples db_connections, entonces
    # podríamos mantener la M-M y añadir una nota de que para DATABASE_QUERY solo se usa la primera,
    # O la solución de la FK directa es más limpia si esa es la regla.
    # POR AHORA, ASUMIMOS LA FK DIRECTA PARA SIMPLIFICAR Y ALINEAR CON EL FEEDBACK.
    # Tu M-M `db_connections` la eliminaríamos o la renombramos si es para otro propósito.
    # Voy a COMENTAR la relación M-M 'db_connections' que tenías, asumiendo la FK.
    """
    # Relación M-M anterior, la comentamos si db_connection_config_id es la primaria para DATABASE_QUERY
    db_connections_legacy_mm = relationship( 
        "DatabaseConnectionConfig",
        secondary=context_db_connection_association,
        backref="associated_contexts_legacy_mm", # Nombre diferente para evitar colisión con el nuevo backref
        lazy="selectin"
    )
    """
    # === FIN CAMBIOS/NUEVOS CAMPOS DE RELACIÓN ===

    document_sources = relationship( # Relación M-M con DocumentSourceConfig se mantiene
        "DocumentSourceConfig", 
        secondary=context_document_source_association,
        backref="associated_contexts", # Nombre ajustado para claridad
        lazy="selectin"
    )
    role_permissions = relationship(
        "RoleContextPermission", 
        back_populates="context_definition", 
        cascade="all, delete-orphan"
    )
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ContextDefinition(id={self.id}, name='{self.name}', type='{self.main_type.value}')>"