# app/schemas/schemas.py

import enum
import json
from pydantic import (
    BaseModel, Field, constr, field_validator, EmailStr, ConfigDict, 
    model_validator, ValidationInfo # Asegúrate que ValidationInfo se importa si la usas
)
from typing import List, Optional, Dict, Any, Union
import datetime
# === IMPORTACIÓN DE ENUMS DESDE MODELOS SQLAlchemy ===
from app.models.context_definition import ContextMainType as SQLA_ContextMainType
from app.models.document_source_config import SupportedDocSourceType as SQLA_SupportedDocSourceType
from app.models.db_connection_config import SupportedDBType as SQLA_SupportedDBType # <--- ASEGÚRATE QUE ESTA LÍNEA ESTÁ ACTIVA Y ES CORRECTA

# === IMPORTACIÓN DE ENUMS DESDE MODELOS SQLAlchemy ===
from app.models.context_definition import ContextMainType as SQLA_ContextMainType
# ... (otros imports de SQLA Enums)
from app.models.document_source_config import SupportedDocSourceType as SQLA_SupportedDocSourceType # <-- DEBE ESTAR ACTIVO

# app/schemas/schemas.py

import enum
import json
from pydantic import (
    BaseModel, Field, constr, field_validator, EmailStr, ConfigDict, 
    model_validator, ValidationInfo
)
from typing import List, Optional, Dict, Any, Union
import datetime

# === IMPORTACIÓN DE ENUMS DESDE MODELOS SQLAlchemy ===
from app.models.context_definition import ContextMainType as SQLA_ContextMainType
from app.models.document_source_config import SupportedDocSourceType as SQLA_SupportedDocSourceType
from app.models.db_connection_config import SupportedDBType as SQLA_SupportedDBType

# ESTAS IMPORTACIONES SON IMPORTANTES PARA LOS ENUMS LLMProviderType y LLMModelType
try:
    from app.models.llm_model_config import LLMProviderType as SQLA_LLMProviderType
    from app.models.llm_model_config import LLMModelType as SQLA_LLMModelType
except ImportError:
    print("SCHEMA_PY WARNING: Could not import Enums from app.models.llm_model_config. Using placeholders.")
    class SQLA_LLMProviderType(str, enum.Enum):
        GOOGLE = "GOOGLE"; OPENAI = "OPENAI"; AZURE_OPENAI = "AZURE_OPENAI"; ANTHROPIC = "ANTHROPIC"; HUGGINGFACE_LOCAL="HUGGINGFACE_LOCAL"; OLLAMA="OLLAMA"; CUSTOM = "CUSTOM"
    class SQLA_LLMModelType(str, enum.Enum):
        CHAT_COMPLETION = "CHAT_COMPLETION"; TEXT_GENERATION = "TEXT_GENERATION"; EMBEDDING = "EMBEDDING"

# --- ENUMS PARA PYDANTIC (derivados de los Enums SQLAlchemy) ---

# === ASEGÚRATE QUE ESTAS DEFINICIONES DE ENUM PYDANTIC ESTÉN DESCOMENTADAS Y ANTES DE LLMModelConfigBase ===
class LLMProviderType(str, enum.Enum): # <--- DEBE ESTAR DEFINIDO AQUÍ
    GOOGLE = SQLA_LLMProviderType.GOOGLE.value
    OPENAI = SQLA_LLMProviderType.OPENAI.value
    AZURE_OPENAI = SQLA_LLMProviderType.AZURE_OPENAI.value
    ANTHROPIC = SQLA_LLMProviderType.ANTHROPIC.value
    HUGGINGFACE_LOCAL = SQLA_LLMProviderType.HUGGINGFACE_LOCAL.value
    OLLAMA = SQLA_LLMProviderType.OLLAMA.value
    CUSTOM = SQLA_LLMProviderType.CUSTOM.value

class LLMModelType(str, enum.Enum): # <--- DEBE ESTAR DEFINIDO AQUÍ
    CHAT_COMPLETION = SQLA_LLMModelType.CHAT_COMPLETION.value
    TEXT_GENERATION = SQLA_LLMModelType.TEXT_GENERATION.value
    EMBEDDING = SQLA_LLMModelType.EMBEDDING.value
    # IMAGE_ANALYSIS = SQLA_LLMModelType.IMAGE_ANALYSIS.value # Comentado
# === FIN ENUMS LLM ===

class DocSourceType(str, enum.Enum): # ... (ya activo) ...
    LOCAL_FOLDER = SQLA_SupportedDocSourceType.LOCAL_FOLDER.value
    S3_BUCKET = SQLA_SupportedDocSourceType.S3_BUCKET.value
    AZURE_BLOB = SQLA_SupportedDocSourceType.AZURE_BLOB.value
    WEB_URL_SINGLE = SQLA_SupportedDocSourceType.WEB_URL_SINGLE.value

class DBType(str, enum.Enum): # ... (ya activo) ...
    POSTGRESQL = SQLA_SupportedDBType.POSTGRESQL.value
    SQLSERVER = SQLA_SupportedDBType.SQLSERVER.value
    MYSQL = SQLA_SupportedDBType.MYSQL.value
    ORACLE = SQLA_SupportedDBType.ORACLE.value

class ContextMainType(str, enum.Enum): # ... (ya activo) ...
    DOCUMENTAL = SQLA_ContextMainType.DOCUMENTAL.value
    DATABASE_QUERY = SQLA_ContextMainType.DATABASE_QUERY.value
    # IMAGE_ANALYSIS = "IMAGE_ANALYSIS" # Comentado

 
# =====================================================
# --- SCHEMAS BASE REUTILIZABLES (DEBE ESTAR AQUÍ ARRIBA) ---
# =====================================================
class OrmBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

# =====================================================
# --- SCHEMAS PARA ApiClientSettings (YA DESCOMENTADO)---
# =====================================================
class ApiClientSettingsSchema(BaseModel):
    # ... (definición completa)
    application_id: str = Field(min_length=3, max_length=100, description="ID de la aplicación cliente que usa esta API Key (para header X-Application-ID).")
    allowed_context_ids: List[int] = Field(default_factory=list, description="IDs de los ContextDefinitions permitidos.")
    is_web_client: bool = Field(False, description="True si es un cliente web (para CORS).")
    allowed_web_origins: List[str] = Field(default_factory=list, description="Orígenes web permitidos (ej. 'https://app.com') si is_web_client es true.")
    human_handoff_agent_group_id: Optional[int] = Field(None, description="ID del HumanAgentGroup para handoff (override).")
    default_llm_model_config_id_override: Optional[int] = Field(None, description="Override del LLMModelConfig del contexto/agente virtual.")
    default_virtual_agent_profile_id_override: Optional[int] = Field(None, description="Override del VirtualAgentProfile del contexto.")
    history_k_messages: int = Field(5, ge=0, le=50, description="Mensajes de historial a considerar por el LLM.")
    max_tokens_per_response_override: Optional[int] = Field(None, ge=1, le=8000, description="Override de max_tokens para la respuesta del LLM.")


# =====================================================
# --- SCHEMAS PARA API CLIENT (YA DESCOMENTADO) ---
# =====================================================
class ContextDefinitionBriefForApiClient(OrmBaseModel): # Usa OrmBaseModel
    id: int
    name: str
    main_type: ContextMainType

class ApiClientBase(BaseModel): # No necesita OrmBaseModel aquí si no hace from_attributes directo
    name: constr(min_length=3, max_length=100)
    description: Optional[str] = None
    is_active: bool = Field(True)
    settings: ApiClientSettingsSchema = Field(default_factory=ApiClientSettingsSchema)

class ApiClientCreate(ApiClientBase):
    pass

class ApiClientUpdate(BaseModel):
    name: Optional[constr(min_length=3, max_length=100)] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    settings: Optional[ApiClientSettingsSchema] = None

class ApiClientResponse(ApiClientBase, OrmBaseModel): # Usa OrmBaseModel
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    allowed_contexts_details: List[ContextDefinitionBriefForApiClient] = Field(default_factory=list)

class ApiClientWithPlainKeyResponse(ApiClientResponse): # Usa OrmBaseModel indirectamente
    api_key_plain: Optional[str] = Field(None)


# ==============================================================================
# === DESCOMENTA ESTA SECCIÓN (ContextDefinition y sus dependencias internas) ===
# ==============================================================================

# --- ASUMIMOS QUE LOS ENUMS Y OTROS SCHEMAS BASE YA ESTÁN ARRIBA Y ACTIVOS ---
# Como LLMModelConfigResponse, VirtualAgentProfileResponse, DocumentSourceResponse, DatabaseConnectionResponse si se usan en ContextDefinitionResponse.
# Si ContextDefinitionResponse los necesita, DEBES DESCOMENTAR ESOS PRIMERO.

# Placeholder para estos schemas si aún no están descomentados:
# class LLMModelConfigResponse(BaseModel): pass # TEMPORAL
# class VirtualAgentProfileResponse(BaseModel): pass # TEMPORAL
# class DocumentSourceResponse(BaseModel): pass # TEMPORAL
# class DatabaseConnectionResponse(BaseModel): pass # TEMPORAL

# === SCHEMAS PARA CONTEXTDEFINITION ===
class SqlColumnAccessPolicySchema(BaseModel): # No necesita OrmBaseModel
    allowed_columns: List[str] = Field(default_factory=list, description="Columnas explícitamente permitidas.")
    forbidden_columns: List[str] = Field(default_factory=list, description="Columnas explícitamente prohibidas (prioridad sobre allowed).")

class SqlTableAccessRuleSchema(BaseModel): # No necesita OrmBaseModel
    table_name: constr(min_length=1) = Field(..., description="Nombre de la tabla (ej. 'esquema.tabla').")
    column_policy: Optional[SqlColumnAccessPolicySchema] = Field(None, description="Política de columnas si no es acceso total/nulo.")

class SqlSelectPolicySchema(BaseModel): # No necesita OrmBaseModel
    default_select_limit: int = Field(10, ge=0, le=1000, description="Límite de filas por defecto para SELECT.")
    max_select_limit: int = Field(50, ge=0, le=2000, description="Límite máximo de filas permitido para SELECT.")
    allow_joins: bool = True
    allowed_join_types: List[str] = Field(default_factory=lambda: ["INNER", "LEFT", "RIGHT", "FULL OUTER"])
    allow_aggregations: bool = True
    allowed_aggregation_functions: List[str] = Field(default_factory=lambda: ["COUNT", "SUM", "AVG", "MIN", "MAX"])
    allow_group_by: bool = True
    allow_order_by: bool = True
    allow_where_clauses: bool = True
    forbidden_keywords_in_where: List[str] = Field(default_factory=lambda: ["DELETE", "UPDATE", "INSERT", "DROP", "TRUNCATE", "EXEC", "ALTER", "CREATE", "GRANT", "REVOKE"])
    column_access_rules: List[SqlTableAccessRuleSchema] = Field(default_factory=list, description="Reglas de acceso a columnas por tabla.")
    llm_instructions_for_select: List[str] = Field(default_factory=list, description="Instrucciones adicionales para el LLM al generar SQL.")

class DatabaseQueryProcessingConfigSchema(BaseModel): # No necesita OrmBaseModel
    schema_info_type: str = Field("dictionary_table_sqlserver_custom", description="Método para obtener el schema de la BD.")
    dictionary_table_query: Optional[str] = Field(None, description="Query para obtener el diccionario de tablas y columnas (si schema_info_type lo requiere).")
    selected_schema_tables_for_llm: List[str] = Field(default_factory=list, description="Tablas seleccionadas (schema.tabla) para exponer al LLM.")
    custom_table_descriptions: Dict[str, str] = Field(default_factory=dict, description="Descripciones personalizadas para tablas (schema.tabla -> descripción).")
    db_schema_chunk_size: int = Field(2000, ge=100, description="Tamaño de chunk para procesar el schema de la BD.")
    db_schema_chunk_overlap: int = Field(200, ge=0, description="Solapamiento entre chunks del schema.")
    sql_select_policy: SqlSelectPolicySchema = Field(default_factory=SqlSelectPolicySchema)

class DocumentalProcessingConfigSchema(BaseModel): # No necesita OrmBaseModel
    chunk_size: int = Field(1000, ge=100)
    chunk_overlap: int = Field(200, ge=0)

 
    
class ContextDefinitionBaseInfo(BaseModel):
    name: constr(min_length=3, max_length=150)
    description: Optional[str] = None
    is_active: bool = Field(True)
    main_type: ContextMainType # El Pydantic Enum
    default_llm_model_config_id: Optional[int] = None # SOLO ID
    virtual_agent_profile_id: Optional[int] = None    # SOLO ID

class ContextDefinitionCreate(ContextDefinitionBaseInfo):
    document_source_ids: List[int] = Field(default_factory=list)
    db_connection_config_id: Optional[int] = Field(None, description="ID de la DBConnection si main_type es DATABASE_QUERY.")
    processing_config_documental: Optional[DocumentalProcessingConfigSchema] = None
    processing_config_database_query: Optional[DatabaseQueryProcessingConfigSchema] = None

class ContextDefinitionUpdate(BaseModel):
    name: Optional[constr(min_length=3, max_length=150)] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    main_type: Optional[ContextMainType] = None 
    default_llm_model_config_id: Optional[int] = None # SOLO ID
    virtual_agent_profile_id: Optional[int] = None    # SOLO ID
    document_source_ids: Optional[List[int]] = None
    db_connection_config_id: Optional[int] = Field(None) # SOLO ID
    
    # Configs estructurados para update
    processing_config_documental: Optional[DocumentalProcessingConfigSchema] = None
    processing_config_database_query: Optional[DatabaseQueryProcessingConfigSchema] = None
    # NO debe haber un campo 'processing_config' genérico aquí
    # NO debe haber un 'default_llm_model: string'
    # NO debe haber un 'db_connection_ids'    
# ANTES DE DESCOMENTAR ContextDefinitionResponse, asegúrate que LLMModelConfigResponse, etc., están definidos o descomentados.

# --- SCHEMAS PARA DocumentSourceConfig ---
class DocumentSourceBase(BaseModel):
    name: constr(min_length=3, max_length=100) = Field(description="Nombre de la fuente de documentos.")
    description: Optional[str] = None
    source_type: DocSourceType = Field(description="Tipo de fuente (ej. LOCAL_FOLDER, S3_BUCKET).") # <--- Ahora debería encontrar DocSourceType
    path_or_config: Dict[str, Any] = Field(description="Para LOCAL_FOLDER: {'path':'/ruta'}, para S3: {'bucket':'nombre', 'prefix':'ruta/'}")
    sync_frequency_cron: Optional[str] = Field(None, pattern=r"^((\*|[0-9,-/\?LW#]+)\s*){5,6}$", description="Expresión CRON para sincronización.")

class DocumentSourceCreate(DocumentSourceBase):
    credentials_info: Optional[Dict[str, str]] = Field(None)

class DocumentSourceUpdate(BaseModel):
    name: Optional[constr(min_length=3, max_length=100)] = None
    description: Optional[str] = None
    source_type: Optional[DocSourceType] = None
    path_or_config: Optional[Dict[str, Any]] = None
    credentials_info: Optional[Dict[str, str]] = None
    sync_frequency_cron: Optional[str] = Field(None, pattern=r"^((\*|[0-9,-/\?LW#]+)\s*){5,6}$")

class DocumentSourceResponse(DocumentSourceBase, OrmBaseModel): # Usa OrmBaseModel
    id: int
    last_synced_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
# === FIN SECCIÓN DocumentSource ===

# --- SCHEMAS PARA DatabaseConnectionConfig ---
class DatabaseConnectionBase(BaseModel):
    name: constr(min_length=3, max_length=100) = Field(description="Nombre de la conexión a la BD.")
    description: Optional[str] = None
    db_type: DBType = Field(description="Tipo de base de datos (ej. POSTGRESQL).") # DBType Enum debe estar definido
    host: str
    port: int = Field(gt=0, lt=65536)
    database_name: str = Field(description="Nombre de la base de datos.")
    username: str
    extra_params: Dict[str, Any] = Field(default_factory=dict, description="Parámetros adicionales para la cadena de conexión (ej. {'sslmode': 'require'}).")

class DatabaseConnectionCreate(DatabaseConnectionBase):
    password: Optional[str] = Field(None, min_length=1, description="Contraseña para la conexión. No se almacena, se usa para generar URI y luego se descarta.")

class DatabaseConnectionUpdate(BaseModel):
    name: Optional[constr(min_length=3, max_length=100)] = None
    description: Optional[str] = None
    db_type: Optional[DBType] = None
    host: Optional[str] = None
    port: Optional[int] = Field(None, gt=0, lt=65536)
    database_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = Field(None, description="Para actualizar la contraseña (y re-encriptar URI).")
    extra_params: Optional[Dict[str, Any]] = None
    
class DatabaseConnectionResponse(DatabaseConnectionBase, OrmBaseModel): # Usa OrmBaseModel
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
# === FIN SECCIÓN DatabaseConnection ===

# --- SCHEMAS PARA LLMModelConfig ---
class LLMModelConfigBase(BaseModel):
    model_identifier: constr(min_length=1, max_length=255) = Field(..., description="Identificador del modelo (ej. 'gemini-1.5-pro-latest').")
    display_name: constr(min_length=3, max_length=150) = Field(..., description="Nombre amigable para UI.")
    provider: LLMProviderType = Field(..., description="Proveedor del LLM.") # <--- Ahora debería encontrar LLMProviderType
    model_type: LLMModelType = Field(LLMModelType.CHAT_COMPLETION, description="Tipo de tarea del LLM.") # <--- Y LLMModelType
    # ... resto de LLMModelConfigBase ...
    is_active: bool = Field(True)
    api_key_env_var: Optional[str] = Field(None, max_length=100)
    base_url: Optional[str] = Field(None, max_length=512)
    default_temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    default_max_tokens: Optional[int] = Field(2048, ge=1)
    supports_system_prompt: bool = Field(True)
    config_json: Dict[str, Any] = Field(default_factory=dict, description="Configuración JSON específica del proveedor.")

class LLMModelConfigCreate(LLMModelConfigBase):
    pass

class LLMModelConfigUpdate(BaseModel):
    model_identifier: Optional[constr(min_length=1, max_length=255)] = None
    display_name: Optional[constr(min_length=3, max_length=150)] = None
    provider: Optional[LLMProviderType] = None
    model_type: Optional[LLMModelType] = None
    is_active: Optional[bool] = None
    api_key_env_var: Optional[str] = None
    base_url: Optional[str] = None
    default_temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    default_max_tokens: Optional[int] = Field(None, ge=1)
    supports_system_prompt: Optional[bool] = None
    config_json: Optional[Dict[str, Any]] = None

class LLMModelConfigResponse(LLMModelConfigBase, OrmBaseModel): # Usa OrmBaseModel
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
# === FIN SECCIÓN LLMModelConfig ===

# --- SCHEMAS PARA VirtualAgentProfile ---
class VirtualAgentProfileBase(BaseModel):
    name: constr(min_length=3, max_length=150) = Field(..., description="Nombre del perfil de agente.")
    description: Optional[str] = Field(None)
    user_provided_goal_description: Optional[str] = Field(None, description="Objetivo para generación asistida de prompt.")
    system_prompt: str = Field(...)
    llm_model_config_id: int = Field(..., description="ID del LLMModelConfig asociado.") # Referencia a LLMModelConfig
    temperature_override: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens_override: Optional[int] = Field(None, ge=1)
    is_active: bool = Field(True)

class VirtualAgentProfileCreate(VirtualAgentProfileBase):
    pass

class VirtualAgentProfileUpdate(BaseModel):
    name: Optional[constr(min_length=3, max_length=150)] = None
    description: Optional[str] = None
    user_provided_goal_description: Optional[str] = None
    system_prompt: Optional[str] = None
    llm_model_config_id: Optional[int] = None
    temperature_override: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens_override: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None

class VirtualAgentProfileResponse(VirtualAgentProfileBase, OrmBaseModel): # Usa OrmBaseModel
    id: int
    # Necesita LLMModelConfigResponse definido arriba
    llm_model_config: Optional[LLMModelConfigResponse] = Field(None, description="Detalles del modelo LLM asociado (poblado).")
    created_at: datetime.datetime
    updated_at: datetime.datetime
# === FIN SECCIÓN VirtualAgentProfile ===

# --- SCHEMAS PARA HumanAgentGroup y HumanAgent (NUEVO) ---
class HumanAgentGroupBase(BaseModel):
    name: constr(min_length=3, max_length=100) = Field(..., description="Nombre del grupo de agentes humanos.")
    description: Optional[str] = Field(None)
    is_active: bool = Field(True)

class HumanAgentGroupCreate(HumanAgentGroupBase):
    pass

class HumanAgentGroupUpdate(BaseModel):
    name: Optional[constr(min_length=3, max_length=100)] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class HumanAgentGroupResponse(HumanAgentGroupBase, OrmBaseModel): # Usa OrmBaseModel
    id: int
    # agents: List['HumanAgentResponse'] = Field(default_factory=list) # Si se necesita y se maneja forward ref

class HumanAgentBase(BaseModel):
    full_name: constr(min_length=3, max_length=150) = Field(..., description="Nombre completo del agente.")
    email: EmailStr
    teams_id: Optional[str] = Field(None, max_length=255)
    is_available: bool = Field(True) 
    availability_config_json: Dict[str, Any] = Field(default_factory=dict, description="Config JSON para horarios, calendario, etc.")

class HumanAgentCreate(HumanAgentBase):
    group_ids: List[int] = Field(default_factory=list, description="IDs de los HumanAgentGroups a los que pertenecerá.")

class HumanAgentUpdate(BaseModel):
    full_name: Optional[constr(min_length=3, max_length=150)] = None
    email: Optional[EmailStr] = None
    teams_id: Optional[str] = Field(None, max_length=255)
    is_available: Optional[bool] = None
    availability_config_json: Optional[Dict[str, Any]] = None
    group_ids: Optional[List[int]] = None

class HumanAgentResponse(HumanAgentBase, OrmBaseModel): # Usa OrmBaseModel
    id: int
    groups: List[HumanAgentGroupResponse] = Field(default_factory=list) # Necesita HumanAgentGroupResponse definido arriba
    created_at: datetime.datetime
    updated_at: datetime.datetime
# === FIN SECCIÓN HumanAgentGroup y HumanAgent ===

# --- SCHEMAS PARA CHAT ---
class ChatRequest(BaseModel):
    dni: str = Field(min_length=8, max_length=20, description="Identificador del usuario final.")
    message: str = Field(min_length=1, description="Mensaje del usuario.")

class ChatResponse(BaseModel):
    dni: str
    original_message: str
    bot_response: str
    metadata_details_json: Optional[Dict[str, Any]] = Field(default=None, validation_alias="metadata_details", serialization_alias="metadata_details_json", description="Información de trazabilidad (fuentes, SQL, etc.)")
    
    model_config = ConfigDict(populate_by_name=True) # Asegúrate que este ConfigDict es el correcto para Pydantic V2 si lo usas
# === FIN SECCIÓN CHAT ===

class ContextDefinitionResponse(ContextDefinitionBaseInfo, OrmBaseModel):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    
    # Relaciones completas (objetos)
    document_sources: List[DocumentSourceResponse] = Field(default_factory=list)
    db_connection: Optional[DatabaseConnectionResponse] = None # Nota: 'db_connection', singular
    default_llm_model_config: Optional[LLMModelConfigResponse] = None
    virtual_agent_profile: Optional[VirtualAgentProfileResponse] = None
    
    # Campos parseados con alias (el nombre de serialización es lo que Orval verá)
    processing_config_documental_parsed: Optional[DocumentalProcessingConfigSchema] = Field(None, validation_alias="processing_config_documental_from_db", serialization_alias="processing_config_documental")
    processing_config_database_query_parsed: Optional[DatabaseQueryProcessingConfigSchema] = Field(None, validation_alias="processing_config_database_query_from_db", serialization_alias="processing_config_database_query")
    raw_processing_config_from_db: Optional[Dict[str, Any]] = Field(None, validation_alias="processing_config", serialization_alias="processing_config_raw") # Añadí serialization_alias para claridad
    
    
# --- SCHEMAS PARA USER (USUARIOS FINALES DEL CHATBOT) ---
class UserBase(BaseModel): # No hereda de OrmBaseModel para Create/Update
    dni: constr(min_length=8, max_length=20) = Field(description="DNI del usuario final, clave única.")
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    role: str = Field("user", description="Rol del usuario final (para futuras segmentaciones).")

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase, OrmBaseModel): # Usa OrmBaseModel
    id: int
    is_active: bool = Field(True) # Asumo que quieres un default aquí si no viene de la BD
# === FIN SECCIÓN USER ===