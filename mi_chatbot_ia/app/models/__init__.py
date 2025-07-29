# app/models/__init__.py

# Modelos existentes
from .api_client import ApiClient
from .app_user import AppUser # Si tienes una tabla de asociación user_role_assoc diferente a user_role_association, impórtala también.
from .db_connection_config import DatabaseConnectionConfig, SupportedDBType
from .document_source_config import DocumentSourceConfig, SupportedDocSourceType
from .interaction_log import InteractionLog
from .role import Role
from .user_role_association import user_role_association # Esta es la tabla de asociación AppUser <-> Role
from .chat_message_history import ChatMessageHistoryV2 # O como se llame tu modelo de historial
from .admin_panel import AdminPanelMenu, AdminRoleMenuPermission

# Modelo ContextDefinition y sus dependencias
from .context_definition import (
    ContextDefinition, 
    ContextMainType, 
    context_document_source_association, # Tabla M-M para Documentos sigue siendo necesaria
    # context_db_connection_association # <<--- ELIMINADO / COMENTADO (Asumiendo FK directa en ContextDefinition para DBConnection)
                                         # Si aún necesitas la relación M-M db_connections para otros propósitos, mantenla y ajusta el modelo ContextDefinition.
)

# Nuevos modelos que hemos definido
from .llm_model_config import LLMModelConfig, LLMProviderType, LLMModelType
from .virtual_agent_profile import VirtualAgentProfile
from .human_agent import HumanAgent, HumanAgentGroup, human_agent_group_association # Importar la tabla de asociación M-M Agente <-> Grupo

# =======================================================
# === ¡LA LÍNEA QUE FALTA Y RESUELVE EL ERROR! ===
from .admin_panel import AdminPanelMenu, AdminRoleMenuPermission
# =======================================================
from .context_permission import RoleContextPermission 



# Modelos que usan Base_Vector (tu base de datos vectorial)
# Si Langchain crea y maneja sus tablas (langchain_pg_collection, langchain_pg_embedding) y
# no tienes modelos SQLAlchemy explícitos para ellas que hereden de tu Base_Vector,
# entonces no necesitas importar nada aquí para esas tablas de Langchain.
# from .document import Document, DocumentChunk # Solo si tú has definido estos modelos explícitamente.

# __all__ es opcional. Las importaciones de arriba son suficientes para que SQLAlchemy/Alembic
# descubran los modelos.