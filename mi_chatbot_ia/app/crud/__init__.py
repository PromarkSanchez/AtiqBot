# app/crud/__init__.py

# Importar las funciones o los módulos CRUD para que sean accesibles desde el paquete 'crud'

 
# --- Para ApiClient ---
from .crud_api_client import (
    create_api_client,
    get_api_client_by_id,
    get_api_client_by_name,
    get_api_client_by_hashed_key, # <--- CAMBIADO SI SE RENOMBRÓ EN crud_api_client.py
    get_api_clients,
    update_api_client,
    regenerate_api_key,
    delete_api_client
)

# --- Para ContextDefinition ---
from .crud_context_definition import (
    create_context_definition,
    get_context_definition_by_id,
    get_context_definition_by_name,
    get_context_definitions,
    update_context_definition,
    delete_context_definition
)

# --- Para DocumentSourceConfig ---
from .crud_document_source import (
    create_document_source,
    get_document_source_by_id,
    get_document_source_by_name,
    get_document_sources,
    update_document_source,
    delete_document_source,
    get_decrypted_credentials as get_document_source_decrypted_credentials # Renombrar por claridad
)

# --- Para DatabaseConnectionConfig ---
from .crud_db_connection import (
    create_db_connection,
    get_db_connection_by_id,
    get_db_connection_by_name,
    get_db_connections,
    update_db_connection,
    delete_db_connection,
    get_decrypted_password as get_db_connection_decrypted_password, # Renombrar
    get_db_connection_by_id_sync # Tu función síncrona
)

# --- Para LLMModelConfig (NUEVO) ---
from .crud_llm_model_config import (
    create_llm_model_config,
    get_llm_model_config_by_id,
    get_llm_model_config_by_identifier,
    get_llm_model_configs,
    update_llm_model_config,
    delete_llm_model_config
)

# --- Para VirtualAgentProfile (NUEVO) ---
from .crud_virtual_agent_profile import (
    create_virtual_agent_profile,
    get_virtual_agent_profile_by_id,
    get_virtual_agent_profile_by_name,
    get_virtual_agent_profiles,
    update_virtual_agent_profile,
    delete_virtual_agent_profile
)

# --- Para HumanAgent y HumanAgentGroup (NUEVO) ---
from .crud_human_agent import (
    create_human_agent,
    get_human_agent_by_id,
    get_human_agent_by_email,
    get_human_agents,
    update_human_agent,
    delete_human_agent,
    create_human_agent_group,
    get_human_agent_group_by_id,
    get_human_agent_group_by_name,
    get_human_agent_groups,
    update_human_agent_group,
    delete_human_agent_group
)

from .crud_user import (
    create_user,
    get_user_by_id,
    get_user_by_dni,
    get_users,
    update_user,
    delete_user,
    get_contexts_for_user_dni  # <-- AÑADIR ESTA LÍNEA
)
from .crud_interaction_log import create_interaction_log_async

# Creamos un alias. Ahora create_interaction_log también apunta a la función async.
create_interaction_log = create_interaction_log_async


# == Si tienes otros CRUDs (ej. para User, Role, AppUser), impórtalos también ==
# from .crud_user import ...
# from .crud_role import ...
# from .crud_app_user import ...

# Opcional: definir __all__ si quieres controlar qué se importa con 'from app.crud import *'
# Pero usualmente se importan nombres específicos.
# __all__ = [
#     "create_api_client", "get_api_client_by_id", ... ,
#     "create_context_definition", ... ,
#     # etc.
# ]