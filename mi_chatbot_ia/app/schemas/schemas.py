# app/schemas/schemas.py

import enum
from enum import Enum # <-- AÑADE ESTA LÍNEA

import json # Aunque no se usa directamente aquí, es común tenerlo cerca de schemas
import datetime
from typing import List, Optional, Dict, Any, Union,Literal
from app.models.app_user import AuthMethod # Necesitamos importar el Enum
import re # <-- Asegúrate de tener este import

from pydantic import (
    BaseModel, Field, constr, EmailStr, ConfigDict,
    model_validator, ValidationInfo, field_validator
)

def to_camel(snake_str: str) -> str:
    """Convierte un string_de_este_tipo a un stringDeEsteTipo."""
    components = snake_str.split('_')
    # Dejamos la primera parte en minúsculas y capitalizamos el resto.
    return components[0] + ''.join(x.title() for x in components[1:])

print("SCHEMA_PY_DEBUG: Pydantic core components imported.")

# === IMPORTACIÓN DE ENUMS DESDE MODELOS SQLAlchemy ===
# Estos son los enums definidos en tus modelos SQLAlchemy (ej. usando SAEnum)
# Los importamos con un alias para distinguirlos claramente de los Pydantic Enums.

_sqla_import_errors = []

try:
    from app.models.context_definition import ContextMainType as SQLA_ContextMainType
    print("SCHEMA_PY_DEBUG: SQLA_ContextMainType imported.")
except ImportError as e:
    _sqla_import_errors.append(f"ContextMainType from app.models.context_definition: {e}")
    class SQLA_ContextMainType(str, enum.Enum): DOCUMENTAL = "DOCUMENTAL"; DATABASE_QUERY = "DATABASE_QUERY"

try:
    from app.models.document_source_config import SupportedDocSourceType as SQLA_SupportedDocSourceType
    print("SCHEMA_PY_DEBUG: SQLA_SupportedDocSourceType imported.")
except ImportError as e:
    _sqla_import_errors.append(f"SupportedDocSourceType from app.models.document_source_config: {e}")
    class SQLA_SupportedDocSourceType(str, enum.Enum): LOCAL_FOLDER = "LOCAL_FOLDER"; S3_BUCKET = "S3_BUCKET"; AZURE_BLOB = "AZURE_BLOB"; WEB_URL_SINGLE = "WEB_URL_SINGLE"

try:
    from app.models.db_connection_config import SupportedDBType as SQLA_SupportedDBType
    print("SCHEMA_PY_DEBUG: SQLA_SupportedDBType imported.")
except ImportError as e:
    _sqla_import_errors.append(f"SupportedDBType from app.models.db_connection_config: {e}")
    class SQLA_SupportedDBType(str, enum.Enum): POSTGRESQL = "POSTGRESQL"; SQLSERVER = "SQLSERVER"; MYSQL = "MYSQL"; ORACLE = "ORACLE"

# --- Manejo robusto de la importación para Enums LLM ---
_SQLA_LLMProviderType_IMPORTED = None
_SQLA_LLMModelType_IMPORTED = None

try:
    from app.models.llm_model_config import LLMProviderType as _SQLA_LLMProviderType_IMPORTED_TEMP
    from app.models.llm_model_config import LLMModelType as _SQLA_LLMModelType_IMPORTED_TEMP
    _SQLA_LLMProviderType_IMPORTED = _SQLA_LLMProviderType_IMPORTED_TEMP
    _SQLA_LLMModelType_IMPORTED = _SQLA_LLMModelType_IMPORTED_TEMP
    print("SCHEMA_PY_INFO: Successfully imported LLM Enums from app.models.llm_model_config.")
except ImportError as e:
    _sqla_import_errors.append(f"LLMProviderType/LLMModelType from app.models.llm_model_config: {e}")
    # ESTE ES EL PRINT QUE ESTAMOS MONITOREANDO
    print(f"SCHEMA_PY_LLM_ENUM_IMPORT_FAILED_NOW_USING_PLACEHOLDERS_ERROR_WAS: {e}")
    class _SQLA_LLMProviderType_Placeholder(str, enum.Enum):
        GOOGLE = "GOOGLE"; 
        OPENAI = "OPENAI"; 
        AZURE_OPENAI = "AZURE_OPENAI"; 
        ANTHROPIC = "ANTHROPIC"
        HUGGINGFACE_LOCAL="HUGGINGFACE_LOCAL"; 
        OLLAMA="OLLAMA"; 
        CUSTOM = "CUSTOM";
        BEDROCK = "BEDROCK";
    class _SQLA_LLMModelType_Placeholder(str, enum.Enum):
        CHAT_COMPLETION = "CHAT_COMPLETION"; TEXT_GENERATION = "TEXT_GENERATION"; EMBEDDING = "EMBEDDING"
    
    _SQLA_LLMProviderType_IMPORTED = _SQLA_LLMProviderType_Placeholder
    _SQLA_LLMModelType_IMPORTED = _SQLA_LLMModelType_Placeholder

if _sqla_import_errors:
    print("SCHEMA_PY_CRITICAL_ERRORS_IMPORTING_FROM_MODELS:")
    for err_msg in _sqla_import_errors:
        print(f"  - {err_msg}")
    print("SCHEMA_PY_CRITICAL_ERRORS_END: Placeholders might be in use for missing enums.")

# --- ENUMS PARA PYDANTIC ---
def _get_enum_value(sqla_enum_member):
    if hasattr(sqla_enum_member, 'value'): return sqla_enum_member.value
    return sqla_enum_member

class LLMProviderType(str, enum.Enum):
    GOOGLE = _get_enum_value(_SQLA_LLMProviderType_IMPORTED.GOOGLE)
    OPENAI = _get_enum_value(_SQLA_LLMProviderType_IMPORTED.OPENAI)
    AZURE_OPENAI = _get_enum_value(_SQLA_LLMProviderType_IMPORTED.AZURE_OPENAI)
    ANTHROPIC = _get_enum_value(_SQLA_LLMProviderType_IMPORTED.ANTHROPIC)
    HUGGINGFACE_LOCAL = _get_enum_value(_SQLA_LLMProviderType_IMPORTED.HUGGINGFACE_LOCAL)
    OLLAMA = _get_enum_value(_SQLA_LLMProviderType_IMPORTED.OLLAMA)
    CUSTOM = _get_enum_value(_SQLA_LLMProviderType_IMPORTED.CUSTOM)
    BEDROCK = _get_enum_value(_SQLA_LLMProviderType_IMPORTED.BEDROCK)   
print("SCHEMA_PY_DEBUG: Pydantic LLMProviderType defined.")

class LLMModelType(str, enum.Enum):
    CHAT_COMPLETION = _get_enum_value(_SQLA_LLMModelType_IMPORTED.CHAT_COMPLETION)
    TEXT_GENERATION = _get_enum_value(_SQLA_LLMModelType_IMPORTED.TEXT_GENERATION)
    EMBEDDING = _get_enum_value(_SQLA_LLMModelType_IMPORTED.EMBEDDING)
print("SCHEMA_PY_DEBUG: Pydantic LLMModelType defined.")

class DocSourceType(str, enum.Enum):
    LOCAL_FOLDER = _get_enum_value(SQLA_SupportedDocSourceType.LOCAL_FOLDER)
    S3_BUCKET = _get_enum_value(SQLA_SupportedDocSourceType.S3_BUCKET)
    AZURE_BLOB = _get_enum_value(SQLA_SupportedDocSourceType.AZURE_BLOB)
    WEB_URL_SINGLE = _get_enum_value(SQLA_SupportedDocSourceType.WEB_URL_SINGLE)
print("SCHEMA_PY_DEBUG: Pydantic DocSourceType defined.")

class DBType(str, enum.Enum):
    POSTGRESQL = _get_enum_value(SQLA_SupportedDBType.POSTGRESQL)
    SQLSERVER = _get_enum_value(SQLA_SupportedDBType.SQLSERVER)
    MYSQL = _get_enum_value(SQLA_SupportedDBType.MYSQL)
    ORACLE = _get_enum_value(SQLA_SupportedDBType.ORACLE)
print("SCHEMA_PY_DEBUG: Pydantic DBType defined.")

class ContextMainType(str, enum.Enum):
    DOCUMENTAL = _get_enum_value(SQLA_ContextMainType.DOCUMENTAL)
    DATABASE_QUERY = _get_enum_value(SQLA_ContextMainType.DATABASE_QUERY)
print("SCHEMA_PY_DEBUG: Pydantic ContextMainType defined.")
 
# =====================================================
# --- SCHEMAS BASE REUTILIZABLES ---
# =====================================================
class OrmBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
print("SCHEMA_PY_DEBUG: OrmBaseModel defined.")

# =====================================================
# --- SCHEMAS PARA LLMModelConfig (Requerido por otros) ---
# =====================================================
class LLMModelConfigBase(BaseModel):
    model_identifier: constr(min_length=1, max_length=255)
    display_name: constr(min_length=3, max_length=150)
    provider: LLMProviderType 
    model_type: LLMModelType = Field(LLMModelType.CHAT_COMPLETION)
    is_active: bool = Field(True)
    base_url: Optional[str] = Field(None)
    default_temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    default_max_tokens: Optional[int] = Field(2048, ge=1)
    supports_system_prompt: bool = Field(True)
    # [CAMBIO CLAVE]: Permitimos explícitamente None y le damos un valor por defecto
    config_json: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    # Validador explícito que SÍ funciona. Si el valor es None, lo convierte en {}.
    @field_validator("config_json", mode="before")
    @classmethod
    def set_config_json_default(cls, value):
        if value is None:
            return {}
        return value


class LLMModelConfigCreate(LLMModelConfigBase):
    api_key_plain: Optional[str] = Field(None, description="API Key en texto plano. Se encriptará antes de guardar.")

class LLMModelConfigUpdate(BaseModel):
    model_identifier: Optional[constr(min_length=1, max_length=255)] = None
    display_name: Optional[constr(min_length=3, max_length=150)] = None
    provider: Optional[LLMProviderType] = None
    model_type: Optional[LLMModelType] = None
    is_active: Optional[bool] = None
    base_url: Optional[str] = None
    default_temperature: Optional[float] = None
    default_max_tokens: Optional[int] = None
    supports_system_prompt: Optional[bool] = None
    config_json: Optional[Dict[str, Any]] = None
    api_key_plain: Optional[str] = Field(None, description="Proporcionar una nueva API Key para actualizarla.")

class LLMModelConfigResponse(LLMModelConfigBase, OrmBaseModel):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    has_api_key: bool = False

print("SCHEMA_PY_DEBUG: LLMModelConfig schemas refactorizados para encriptación.")

# ... (el resto de tus schemas sin cambios) ...


# =====================================================
# --- SCHEMAS PARA VirtualAgentProfile ---
# =====================================================


class VirtualAgentProfileBase(BaseModel):
    name: constr(min_length=3, max_length=150) = Field(...)
    description: Optional[str] = None
    user_provided_goal_description: Optional[str] = None
    system_prompt: str = Field(..., min_length=1)
    
    # <<< --- ¡CAMPOS NUEVOS AÑADIDOS! ---
    greeting_prompt: Optional[str] = None
    name_confirmation_prompt: Optional[str] = None
    # --- FIN DE CAMPOS NUEVOS ---

    llm_model_config_id: int = Field(...)
    temperature_override: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens_override: Optional[int] = Field(None, ge=1)
    is_active: bool = Field(True)
    # === AÑADE ESTAS DOS LÍNEAS AQUÍ ===
    default_user_role: Optional[str] = Field("Usuario", max_length=100)
    fallback_prompt: Optional[str] = None
    # ==================================

class VirtualAgentProfileCreate(VirtualAgentProfileBase):
    # La herencia es suficiente, pero por claridad, podríamos definir los campos aquí
    # pass # Es funcional, pero lo siguiente es más explícito
    name: str
    description: Optional[str] = None
    llm_model_config_id: int
    system_prompt: Optional[str] = None # Los prompts los genera el sistema, así que pueden llegar vacíos
    greeting_prompt: Optional[str] = None
    name_confirmation_prompt: Optional[str] = None
    character_sheet_json: Optional[Dict[str, Any]] = None
    
class VirtualAgentProfileUpdate(BaseModel):
    name: Optional[constr(min_length=3, max_length=150)] = None
    description: Optional[str] = None
    user_provided_goal_description: Optional[str] = None
    system_prompt: Optional[str] = Field(None, min_length=1)

    # <<< --- ¡CAMPOS NUEVOS AÑADIDOS TAMBIÉN AQUÍ! ---
    greeting_prompt: Optional[str] = None
    name_confirmation_prompt: Optional[str] = None
    character_sheet_json: Optional[Dict[str, Any]] = None
    # --- FIN DE CAMPOS NUEVOS ---

    llm_model_config_id: Optional[int] = None
    temperature_override: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens_override: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    # === AÑADE ESTAS DOS LÍNEAS AQUÍ ===
    default_user_role: Optional[str] = Field(None, max_length=100)
    fallback_prompt: Optional[str] = None
    # ==================================

class VirtualAgentProfileResponse(VirtualAgentProfileBase, OrmBaseModel):
    id: int
    llm_model_config: Optional[LLMModelConfigResponse] = None
    character_sheet_json: Optional[Dict[str, Any]] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    # Hereda automáticamente los nuevos campos de VirtualAgentProfileBase

print("SCHEMA_PY_DEBUG: VirtualAgentProfile schemas defined.")

# app/schemas/schemas.py

# ... tus otros schemas

class GeneratedPromptSetResponse(BaseModel):
    """
    Schema para la respuesta del generador de prompts.
    Contiene el conjunto completo de prompts para un agente.
    """
    greeting_prompt: str
    name_confirmation_prompt: str
    system_prompt: str
class GeneratePromptRequest(BaseModel):
    user_description: str = Field(..., min_length=10, max_length=5000, description="La descripción simple en lenguaje natural del objetivo del agente.")
    llm_model_config_id: int = Field(..., description="ID del LLMModelConfig que se usará como 'LLM maestro' para generar el prompt.")

class GeneratedPromptResponse(BaseModel):
    optimized_prompt: str = Field(..., description="El system prompt robusto y optimizado, generado por el LLM maestro.")

print("SCHEMA_PY_DEBUG: Prompt Generation Assistant schemas defined.")

# =====================================================
# --- SCHEMAS PARA DocumentSourceConfig ---
# =====================================================
class DocumentSourceBase(BaseModel):
    name: constr(min_length=3, max_length=100) = Field(...)
    description: Optional[str] = None
    source_type: DocSourceType
    
    # --- CAMBIO CLAVE: Usar Union para permitir string u objeto ---
    path_or_config: Union[Dict[str, Any], str] = Field(..., description="Ruta (string) o configuración (JSON object) según el source_type.")
    is_active: bool = Field(True) 
    sync_frequency_cron: Optional[str] = Field(None, pattern=r"^((\*|[0-9,-/\?LW#]+)\s*){5,6}$")
    
    # --- VALIDADOR para asegurar consistencia entre tipo y configuración ---
    @model_validator(mode='before')
    @classmethod
    def check_path_or_config_type(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data # Dejar que Pydantic maneje errores de tipo base

        source_type = data.get('source_type')
        path_config = data.get('path_or_config')

        if not source_type or path_config is None:
            return data # No hay suficiente información para validar

        # Si el tipo espera un JSON, path_or_config DEBE ser un dict
        json_expected_types = [DocSourceType.S3_BUCKET.value, DocSourceType.AZURE_BLOB.value]
        if source_type in json_expected_types:
            if not isinstance(path_config, dict):
                raise ValueError(f"Para el tipo de fuente '{source_type}', 'path_or_config' debe ser un objeto JSON.")
        
        # Si el tipo espera un string, path_or_config DEBE ser un string
        string_expected_types = [DocSourceType.LOCAL_FOLDER.value, DocSourceType.WEB_URL_SINGLE.value]
        if source_type in string_expected_types:
            if not isinstance(path_config, str):
                raise ValueError(f"Para el tipo de fuente '{source_type}', 'path_or_config' debe ser un string (ruta o URL).")
        
        return data

class DocumentSourceCreate(DocumentSourceBase):
    credentials_info: Optional[Dict[str, str]] = None

class DocumentSourceUpdate(BaseModel):
    name: Optional[constr(min_length=3, max_length=100)] = None
    description: Optional[str] = None
    source_type: Optional[DocSourceType] = None
    
    # --- CAMBIO CLAVE TAMBIÉN AQUÍ ---
    path_or_config: Optional[Union[Dict[str, Any], str]] = None
    
    credentials_info: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None

    sync_frequency_cron: Optional[str] = Field(None, pattern=r"^((\*|[0-9,-/\?LW#]+)\s*){5,6}$")

    # Opcional: Añadir el mismo validador aquí si es necesario para asegurar consistencia en el update.
    # Por simplicidad, se puede omitir si confías en que el frontend envía los datos correctos.

class DocumentSourceResponse(DocumentSourceBase, OrmBaseModel):
    id: int
    last_synced_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    # La respuesta no debe incluir 'credentials_info' por seguridad.
    # Si tu modelo ORM lo tiene, Pydantic no lo incluirá a menos que se defina aquí explícitamente.
    # El `path_or_config` ya está definido en la clase base y se heredará correctamente.

print("SCHEMA_PY_DEBUG: DocumentSourceConfig schemas defined.")


# =====================================================
# --- SCHEMAS PARA DatabaseConnectionConfig ---
# =====================================================
class DatabaseConnectionBase(BaseModel):
    name: constr(min_length=3, max_length=100) = Field(...)
    description: Optional[str] = None
    db_type: DBType
    host: str; port: int = Field(gt=0, lt=65536)
    database_name: str; username: str
    extra_params: Dict[str, Any] = Field(default_factory=dict)

class DatabaseConnectionCreate(DatabaseConnectionBase):
    password: Optional[str] = Field(None, min_length=1)

class DatabaseConnectionUpdate(BaseModel):
    name: Optional[constr(min_length=3, max_length=100)] = None
    description: Optional[str] = None; db_type: Optional[DBType] = None
    host: Optional[str] = None; port: Optional[int] = Field(None, gt=0, lt=65536)
    database_name: Optional[str] = None; username: Optional[str] = None
    password: Optional[str] = None; extra_params: Optional[Dict[str, Any]] = None
    
class DatabaseConnectionResponse(DatabaseConnectionBase, OrmBaseModel):
    id: int; created_at: datetime.datetime; updated_at: datetime.datetime
print("SCHEMA_PY_DEBUG: DatabaseConnectionConfig schemas defined.")
# ==========================================================
# --- NUEVAS DEFINICIONES PARA HERRAMIENTAS (STORED PROCS) ---
# ==========================================================
# app/schemas/schemas.py

# --- AÑADE ESTE NUEVO ENUM AL PRINCIPIO DE LA SECCIÓN DE SCHEMAS ---
class ParamTransformType(str, enum.Enum):
    REMOVE_DASHES = "REMOVE_DASHES" # Para "2024-1" -> "20241"
    TO_UPPER = "TO_UPPER"         # Para "pm001" -> "PM001"
    EXTRACT_NUMBERS = "EXTRACT_NUMBERS" # Para "el código es 001" -> "001"

class EntityResolver(BaseModel):
    """Configuración para resolver texto de usuario a un código oficial."""
    type: str = Field(default="CATALOG", description="Tipo de resolvedor. Actualmente, solo 'CATALOG'.")
    entity_type: str = Field(..., description="El 'tipo_entidad' a buscar en la tabla acad.catalogo_entidades (ej: 'CURSO', 'PERIODO').")

class ToolParameter(BaseModel):
    """Define un parámetro individual para una herramienta de BD."""
    name: str = Field(..., description="Nombre del parámetro (ej: p_scurso). Debe coincidir exactamente con el de la BD.")
    description_for_llm: Optional[str] = Field(None, description="Descripción en lenguaje natural para que el LLM sepa qué buscar en la conversación.")
    is_required: bool = Field(default=True, description="Indica si este parámetro es obligatorio para ejecutar la herramienta.")
    is_dni_param: bool = Field(default=False, description="Marcar como 'true' si este es el parámetro que debe recibir el DNI del usuario logueado.")
    clarification_question: Optional[str] = Field(None, description="Pregunta específica que el bot hará al usuario si este parámetro falta.")
    entity_resolver: Optional[EntityResolver] = Field(None, description="Configuración opcional para resolver la entrada del usuario a un código oficial usando el catálogo de entidades.")
    transformations: List[ParamTransformType] = Field(default_factory=list, description="Lista de transformaciones de formato a aplicar al valor (ej: quitar guiones).")

class StoredProcedureTool(BaseModel):
    """Define un Stored Procedure o Función de BD como una 'Herramienta' completa."""
    tool_name: str = Field(..., description="Nombre único y descriptivo para la herramienta (ej: 'obtener_notas_del_alumno').")
    description_for_llm: str = Field(..., description="Descripción para que un LLM de alto nivel sepa cuándo podría usarse esta herramienta (funcionalidad futura).")
    procedure_name: str = Field(..., description="Nombre completo y real del SP o Función en la BD (ej: 'acad.fn_app_obtener_notas_curso').")
    parameters: List[ToolParameter] = Field(default_factory=list, description="La lista de todos los parámetros que la herramienta necesita.")

# ==========================================================
# --- SCHEMAS PARA LA INSPECCIÓN DE BASE DE DATOS (NUEVO) ---
# ==========================================================
class ColumnInfo(BaseModel):
    name: str = Field(..., description="Nombre de la columna.")
    type: str = Field(..., description="Tipo de dato SQLAlchemy de la columna.")
    nullable: bool = Field(..., description="Indica si la columna permite valores nulos.")

class TableInfo(BaseModel):
    schema_name: Optional[str] = Field(None, description="Nombre del esquema (e.g., 'dbo', 'public').")
    table_name: str = Field(..., description="Nombre de la tabla.")
    full_name: str = Field(..., description="Nombre completo calificado, formato 'esquema.tabla'.")
    columns: List[ColumnInfo] = Field(..., description="Lista de columnas de la tabla.")

class DbInspectionResponse(BaseModel):
    connection_name: str = Field(..., description="Nombre de la conexión que fue inspeccionada.")
    tables: List[TableInfo] = Field(..., description="Lista de tablas encontradas en la base de datos.")

print("SCHEMA_PY_DEBUG: Database Inspection schemas defined.")
# =====================================================
# --- SCHEMAS PARA CONTEXTDEFINITION ---
# =====================================================
class SqlColumnAccessPolicySchema(BaseModel):
    allowed_columns: List[str] = Field(default_factory=list)
    forbidden_columns: List[str] = Field(default_factory=list)

class SqlTableAccessRuleSchema(BaseModel):
    table_name: constr(min_length=1) = Field(...)
    column_policy: Optional[SqlColumnAccessPolicySchema] = None

class SqlSelectPolicySchema(BaseModel): # Modificación aquí
    default_select_limit: int = Field(10, ge=0, le=1000)
    max_select_limit: int = Field(50, ge=0, le=2000)
    allow_joins: bool = True
    allowed_join_types: List[str] = Field(default_factory=lambda: ["INNER", "LEFT", "RIGHT", "FULL OUTER"])
    allow_aggregations: bool = True
    allowed_aggregation_functions: List[str] = Field(default_factory=lambda: ["COUNT", "SUM", "AVG", "MIN", "MAX"])
    allow_group_by: bool = True
    allow_order_by: bool = True
    allow_where_clauses: bool = True
    forbidden_keywords_in_where: List[str] = Field(default_factory=lambda: ["DELETE", "UPDATE", "INSERT", "DROP", "TRUNCATE", "EXEC", "SHUTDOWN"])
    
    allowed_tables_for_select: List[str] = Field(default_factory=list) # Este es el campo que sql_tools usa para las tablas.
    
    # NUEVO: Campo para leer la estructura de diccionario actual de la BD
    column_access_policy_from_db: Optional[Dict[str, SqlColumnAccessPolicySchema]] = Field(
        default=None, 
        validation_alias="column_access_policy" # Para que coincida con la clave en tu JSON de BD
    )
    
    # Mantenemos el campo que el frontend probablemente espera (una lista)
    # Lo popularemos en el @model_validator o en el CRUD _prepare
    column_access_rules: List[SqlTableAccessRuleSchema] = Field(default_factory=list)
    
    llm_instructions_for_select: List[str] = Field(default_factory=list)

    @model_validator(mode='after') # o 'before' si transformas antes de la validación de otros campos
    def transform_column_policy_to_rules(self) -> 'SqlSelectPolicySchema':
        if self.column_access_policy_from_db and not self.column_access_rules: # Solo si rules está vacío y policy_from_db tiene datos
            rules = []
            for table_name, policy_data in self.column_access_policy_from_db.items():
                # Asumimos que policy_data ya es un dict que SqlColumnAccessPolicySchema puede validar
                # o ya es una instancia si Pydantic lo parseó anidado.
                # Para ser seguros, si es un dict, lo validamos.
                policy_obj = policy_data
                if isinstance(policy_data, dict):
                    try:
                        policy_obj = SqlColumnAccessPolicySchema.model_validate(policy_data)
                    except Exception: # Si falla la validación, omitimos o logueamos
                        print(f"SCHEMA_WARNING: No se pudo validar column_policy para tabla '{table_name}' en SqlSelectPolicySchema.")
                        continue 
                
                rules.append(SqlTableAccessRuleSchema(table_name=table_name, column_policy=policy_obj))
            self.column_access_rules = rules
        # No necesitamos devolver 'self' explícitamente en Pydantic V2 para validadores 'after' que modifican self.
        return self

class DatabaseQueryProcessingConfigSchema(BaseModel):
    schema_info_type: str = Field("dictionary_table_sqlserver_custom")
    dictionary_table_query: Optional[str] = None
    selected_schema_tables_for_llm: List[str] = Field(default_factory=list)
    custom_table_descriptions: Dict[str, str] = Field(default_factory=dict)
    db_schema_chunk_size: int = Field(2000, ge=100)
    db_schema_chunk_overlap: int = Field(200, ge=0)
    sql_select_policy: SqlSelectPolicySchema = Field(default_factory=SqlSelectPolicySchema)
    tools: List[StoredProcedureTool] = Field(default_factory=list, description="Lista de SPs/Funciones expuestas como 'Herramientas' al LLM.")
    

class DocumentalProcessingConfigSchema(BaseModel):
    chunk_size: int = Field(1000, ge=100)
    chunk_overlap: int = Field(200, ge=0)
    rag_prompts: Optional[Dict[str,str]] = Field(None, description="Opcional: {'condense_question_template': '...', 'docs_qa_template': '...'}")

class ContextDefinitionBaseInfo(BaseModel):
    name: constr(min_length=3, max_length=150)
    description: Optional[str] = None
    is_active: bool = Field(True)
    is_public: bool = Field(True, comment="Si es True, el contexto es accesible para usuarios no autenticados.") # <-- AÑADIR ESTA LÍNEA
    main_type: ContextMainType
    default_llm_model_config_id: Optional[int] = None
    virtual_agent_profile_id: Optional[int] = None


class ContextDefinitionCreate(ContextDefinitionBaseInfo):
    document_source_ids: List[int] = Field(default_factory=list)
    db_connection_config_id: Optional[int] = None
    processing_config_documental: Optional[DocumentalProcessingConfigSchema] = None
    processing_config_database_query: Optional[DatabaseQueryProcessingConfigSchema] = None

class ContextDefinitionUpdate(BaseModel):
    name: Optional[constr(min_length=3, max_length=150)] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None # <-- AÑADIR ESTA LÍNEA
    main_type: Optional[ContextMainType] = None
    default_llm_model_config_id: Optional[int] = None
    virtual_agent_profile_id: Optional[int] = None
    document_source_ids: Optional[List[int]] = None
    db_connection_config_id: Optional[int] = None
    processing_config_documental: Optional[DocumentalProcessingConfigSchema] = None
    processing_config_database_query: Optional[DatabaseQueryProcessingConfigSchema] = None

class ContextDefinitionResponse(ContextDefinitionBaseInfo, OrmBaseModel):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    document_sources: List[DocumentSourceResponse] = Field(default_factory=list)
    db_connection_config: Optional[DatabaseConnectionResponse] = Field(None, validation_alias="db_connection")
    default_llm_model_config: Optional[LLMModelConfigResponse] = None
    virtual_agent_profile: Optional[VirtualAgentProfileResponse] = None
    processing_config_documental_parsed: Optional[DocumentalProcessingConfigSchema] = Field(None, validation_alias="processing_config_documental_from_db", serialization_alias="processing_config_documental")
    processing_config_database_query_parsed: Optional[DatabaseQueryProcessingConfigSchema] = Field(None, validation_alias="processing_config_database_query_from_db", serialization_alias="processing_config_database_query")
    raw_processing_config_from_db: Optional[Dict[str, Any]] = Field(None, validation_alias="processing_config", serialization_alias="processing_config_raw")
print("SCHEMA_PY_DEBUG: ContextDefinition schemas defined.")

# =====================================================
# --- SCHEMAS PARA ApiClientSettings Y API CLIENT ---
# =====================================================

# --- Componentes del Schema ---
class WebchatUITheme(BaseModel):
    primaryColor: str
    avatarBackgroundColor: str

class WebchatInitialState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"

# ---> ¡NUEVO ENUM PARA EL TEMA! <---
class WebchatThemeMode(str, Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"

# --- Schema Principal (Actualizado) ---
class WebchatUIConfig(BaseModel):
    botName: str
    botDescription: Optional[str] = None
    composerPlaceholder: Optional[str] = None
    theme: WebchatUITheme
    showBetaBadge: Optional[bool] = False
    footerEnabled: Optional[bool] = True
    footerText: Optional[str] = "Powered by AtiqTec"
    footerLink: Optional[str] = "https://atiqtec.com"
    initialState: Optional[WebchatInitialState] = WebchatInitialState.CLOSED
    initialStateText: Optional[str] = "¡Hola! ¿Podemos ayudarte?"
    avatarImageUrl: Optional[str] = None
    floatingButtonImageUrl: Optional[str] = None
    
    # ---> ¡NUEVO CAMPO AÑADIDO! <---
    themeMode: Optional[WebchatThemeMode] = WebchatThemeMode.SYSTEM

    model_config = ConfigDict(alias_generator=to_camel, allow_population_by_field_name=True)

    

class ApiClientSettingsSchema(BaseModel):
    application_id: str = Field(min_length=3, max_length=100)
    allowed_context_ids: List[int] = Field(default_factory=list)
    is_web_client: bool = Field(False)
    allowed_web_origins: List[str] = Field(default_factory=list)
    human_handoff_agent_group_id: Optional[int] = None
    default_llm_model_config_id_override: Optional[int] = None
    default_virtual_agent_profile_id_override: Optional[int] = None
    history_k_messages: int = Field(5, ge=0, le=50)
    max_tokens_per_response_override: Optional[int] = Field(None, ge=1, le=8000)

class ContextDefinitionBriefForApiClient(OrmBaseModel):
    id: int; name: str; main_type: ContextMainType

class ApiClientBase(BaseModel):
    name: constr(min_length=3, max_length=100)
    description: Optional[str] = None; is_active: bool = Field(True)
    settings: ApiClientSettingsSchema
    @model_validator(mode='before')
    @classmethod
    def ensure_settings_default(cls, data: Any) -> Any:
        if isinstance(data, dict) and 'settings' not in data: data['settings'] = ApiClientSettingsSchema()
        return data

class ApiClientCreate(ApiClientBase): pass
class ApiClientUpdate(BaseModel):
    name: Optional[constr(min_length=3, max_length=100)] = None
    description: Optional[str] = None; is_active: Optional[bool] = None
    settings: Optional[ApiClientSettingsSchema] = None

class ApiClientResponse(ApiClientBase, OrmBaseModel):
    id: int; created_at: datetime.datetime; updated_at: datetime.datetime
    allowed_contexts_details: List[ContextDefinitionBriefForApiClient] = Field(default_factory=list)
    webchat_ui_config: Optional[WebchatUIConfig] = None 
    is_premium: bool



class ApiClientWithPlainKeyResponse(ApiClientResponse):
    api_key_plain: Optional[str] = None
print("SCHEMA_PY_DEBUG: ApiClient schemas defined.")

# =====================================================
# --- SCHEMAS PARA HumanAgentGroup y HumanAgent ---
# =====================================================
class HumanAgentGroupBase(BaseModel):
    name: constr(min_length=3, max_length=100) = Field(...)
    description: Optional[str] = None; is_active: bool = Field(True)

class HumanAgentGroupCreate(HumanAgentGroupBase): pass
class HumanAgentGroupUpdate(BaseModel):
    name: Optional[constr(min_length=3, max_length=100)] = None
    description: Optional[str] = None; is_active: Optional[bool] = None

class HumanAgentGroupResponse(HumanAgentGroupBase, OrmBaseModel):
    id: int
    # agents: List['HumanAgentResponse'] = Field(default_factory=list) # Descomentar si es necesario y manejar forward refs

class HumanAgentBase(BaseModel):
    full_name: constr(min_length=3, max_length=150) = Field(...)
    email: EmailStr; teams_id: Optional[str] = Field(None, max_length=255)
    is_available: bool = Field(True)
    availability_config_json: Dict[str, Any] = Field(default_factory=dict)

class HumanAgentCreate(HumanAgentBase):
    group_ids: List[int] = Field(default_factory=list)

class HumanAgentUpdate(BaseModel):
    full_name: Optional[constr(min_length=3, max_length=150)] = None
    email: Optional[EmailStr] = None; teams_id: Optional[str] = Field(None, max_length=255)
    is_available: Optional[bool] = None
    availability_config_json: Optional[Dict[str, Any]] = None
    group_ids: Optional[List[int]] = None

class HumanAgentResponse(HumanAgentBase, OrmBaseModel):
    id: int
    groups: List[HumanAgentGroupResponse] = Field(default_factory=list)
    created_at: datetime.datetime; updated_at: datetime.datetime
print("SCHEMA_PY_DEBUG: HumanAgent schemas defined.")

# app/schemas/schemas.py



# ... (tus otros schemas, como los de AppUser, Roles, etc. van aquí arriba) ...

# ==========================================================
# --- SCHEMAS PARA INTERACCIÓN DEL CHAT (VERSIÓN MEJORADA) ---
# ==========================================================

class ChatRequest(BaseModel):
    """
    Representa la petición que envía el frontend al endpoint de chat.
    Ahora soporta tanto sesiones públicas como autenticadas.
    """
    message: str = Field(min_length=1, description="El mensaje o pregunta del usuario.")
    # Hemos renombrado 'dni' a 'session_id' para que el nombre sea más preciso.
    # En sesiones públicas, será un ID aleatorio. En sesiones autenticadas, puede ser el DNI real.
    session_id: str = Field(min_length=8, max_length=50, description="Identificador único de la sesión de chat.")
    
    # --- CAMPOS NUEVOS PARA EL FLUJO DUAL (Público / Privado) ---
    is_authenticated_user: bool = Field(default=False,description="Indica si la sesión pertenece a un usuario autenticado en el sistema anfitrión (ej. Blackboard).")
    client_settings: Dict = Field(default_factory=dict, exclude=True) # Exclude para no requerirlo desde el frontend

    # 'user_dni' es el DNI real y verificado. Solo se debe enviar si 'is_authenticated_user' es True.
    user_dni: Optional[str] = Field(default=None, min_length=8, max_length=20,description="DNI REAL y verificado del usuario si está autenticado.")
    user_name: Optional[str] = Field(default=None,description="Nombre del usuario, puede ser proporcionado por el frontend en cualquier momento.")
    metadata: Optional[Dict[str, Any]] = Field(default=None,description="Un espacio para metadatos adicionales enviados desde el frontend.")


class ChatResponse(BaseModel):
    """
    Representa la respuesta que el backend envía de vuelta al frontend.
    Renombramos 'dni' a 'session_id' para consistencia.
    """
    session_id: str = Field(description="El mismo session_id de la petición, para que el frontend pueda rastrear la conversación.")
    original_message: str
    bot_response: str
    metadata_details_json: Optional[Dict[str, Any]] = Field(default=None, 
                                                            validation_alias="metadata_details", 
                                                            serialization_alias="metadata_details")
    model_config = ConfigDict(populate_by_name=True)

print("SCHEMA_PY_DEBUG: Chat schemas defined.")

# =====================================================
# --- SCHEMAS PARA USER (USUARIOS FINALES DEL CHATBOT) ---
# ESTA SECCIÓN FUE DESCOMENTADA
# =====================================================
class UserBase(BaseModel):
    dni: constr(min_length=8, max_length=20) = Field(description="DNI del usuario final o ID de sesión.")
    email: Optional[EmailStr] = Field(None, description="Email opcional del usuario final.")
    full_name: Optional[str] = Field(None, max_length=255, description="Nombre completo opcional del usuario final.")
    # `role` es opcional, ya que muchos usuarios pueden no tener uno asignado explícitamente al inicio.
    role: Optional[str] = Field("default_user_role", description="Rol del usuario final para segmentación (ej. 'cliente', 'invitado').")

class UserCreate(UserBase):
    is_active: bool = Field(True, description="Indica si el usuario final está activo en el sistema.")
    # Cualquier otro campo necesario para crear un User, si tu modelo ORM los tiene y no son auto-generados.
    # Por ejemplo, si 'role' fuera obligatorio en la creación.

class UserUpdate(BaseModel): # Solo campos actualizables
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase, OrmBaseModel):
    id: int
    is_active: bool # Debería venir del ORM, no con default aquí
    created_at: datetime.datetime # Asumiendo que el modelo User tiene estos campos
    updated_at: datetime.datetime # Asumiendo que el modelo User tiene estos campos
print("SCHEMA_PY_DEBUG: User (chatbot user) schemas defined.") # <<--- Este print es importante

# =====================================================
# --- SCHEMAS PARA USUARIOS DEL PANEL DE ADMIN (AppUser) ---
# =====================================================
class RoleBriefSchema(OrmBaseModel):
    id: int; name: str
print("SCHEMA_PY_DEBUG: RoleBriefSchema defined.")

class AppUserBase(BaseModel):
    username_ad: constr(min_length=3, max_length=100)
    email: Optional[EmailStr] = None; full_name: Optional[str] = Field(None, max_length=255)
    is_active_local: bool = Field(True)

class AppUserCreate(AppUserBase):
    """Schema específico para crear un usuario LOCAL."""
    password: str = Field(..., min_length=8, description="Contraseña para el nuevo usuario local. Requerido.")
    role_ids: List[int] = Field(default_factory=list, description="Lista de IDs de roles a asignar al crear.")
    # No incluyas 'password' aquí si lo manejas fuera (ej. con AD y no guardas passwords locales)
class AppUserLocalCreate(AppUserBase):
    """Schema para crear un nuevo usuario LOCAL a través de la API."""
    password: str = Field(..., min_length=8, description="Contraseña requerida para el nuevo usuario.")
    role_ids: List[int] = Field(default_factory=list, description="Lista de IDs de los roles a asignar.")

class AppUserUpdate(BaseModel):
    email: Optional[EmailStr] = None; full_name: Optional[str] = Field(None, max_length=255)
    is_active_local: Optional[bool] = None
    role_ids: Optional[List[int]] = Field(None, description="Para actualizar la lista completa de roles asignados.")

class AppUserResponse(AppUserBase, OrmBaseModel):
    id: int; mfa_enabled: bool
    auth_method: AuthMethod # <-- CAMPO AÑADIDO
    roles: List[RoleBriefSchema] = Field(default_factory=list)
    created_at: datetime.datetime; updated_at: datetime.datetime
print("SCHEMA_PY_DEBUG: AppUser schemas defined.")

# =====================================================
# --- SCHEMAS PARA ROLES (del panel de admin) ---
# =====================================================
class RoleBase(BaseModel):
    name: constr(min_length=3, max_length=50)
    description: Optional[str] = Field(None, max_length=255)

class RoleCreate(RoleBase): pass
class RoleUpdate(RoleBase):
    name: Optional[constr(min_length=3, max_length=50)] = None
    description: Optional[str] = Field(None, max_length=255)

class RoleResponse(RoleBase, OrmBaseModel):
    id: int; created_at: datetime.datetime; updated_at: datetime.datetime
print("SCHEMA_PY_DEBUG: Role (admin panel) schemas defined.")

# === REBUILD FORWARD REFERENCES ===
# Si tienes referencias circulares complejas (ej. A usa B, B usa A) y las declaraste como strings
# (ej. `field: 'B'`), necesitarás que Pydantic las resuelva.
all_models_in_module = {name: obj for name, obj in globals().items() if isinstance(obj, type) and issubclass(obj, BaseModel)}
rebuild_errors = []
for model_name, model_cls in all_models_in_module.items():
    if hasattr(model_cls, 'model_rebuild'): # Solo para modelos Pydantic v2+
        try:
            model_cls.model_rebuild(force=True) # El force=True puede ser útil
            # print(f"SCHEMA_PY_DEBUG_REBUILD: Rebuilt model {model_name}")
        except Exception as e_rebuild:
            rebuild_errors.append(f"Could not rebuild model {model_name}. Error: {e_rebuild}")

if rebuild_errors:
    print("SCHEMA_PY_WARNINGS_REBUILDING_MODELS:")
    for err_msg in rebuild_errors:
        print(f"  - {err_msg}")
else:
    print("SCHEMA_PY_INFO: All Pydantic models in module rebuilt (if applicable).")


print("SCHEMA_PY_INFO: >>> app.schemas.schemas module FULLY LOADED. <<<")

# =====================================================
# --- SCHEMAS PARA ADMIN PANEL MENUS Y PERMISOS ---
# =====================================================

class AdminPanelMenuBase(BaseModel):
    name: constr(min_length=3, max_length=100)
    frontend_route: constr(min_length=1, max_length=255)
    icon_name: Optional[str] = Field(None, max_length=100)
    parent_id: Optional[int] = None
    display_order: int = 100

class AdminPanelMenuCreate(AdminPanelMenuBase):
    pass

class AdminPanelMenuUpdate(BaseModel):
    name: Optional[constr(min_length=3, max_length=100)] = None
    frontend_route: Optional[constr(min_length=1, max_length=255)] = None
    icon_name: Optional[str] = Field(None, max_length=100)
    parent_id: Optional[int] = None
    display_order: Optional[int] = None

class AdminPanelMenuResponse(AdminPanelMenuBase, OrmBaseModel):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

class AdminRoleMenuPermissionBase(BaseModel):
    role_id: int
    menu_id: int
    can_view: bool = True
    
class AdminRoleMenuPermissionCreate(BaseModel):
    menu_id: int # El role_id vendrá de la URL
    can_view: bool = True
    
class AdminRoleMenuPermissionResponse(AdminRoleMenuPermissionBase, OrmBaseModel):
    id: int

# Schema específico para el endpoint /me/menus que consumirá el Frontend
class AuthorizedMenuResponse(OrmBaseModel):
    id: int
    name: str
    frontend_route: str
    icon_name: Optional[str]
    parent_id: Optional[int]
    display_order: int
    
print("SCHEMA_PY_DEBUG: Admin Panel Menu schemas defined.")
# FIN DEL BLOQUE A COPIAR

# =====================================================
# --- SCHEMAS PARA AUTENTICACIÓN Y TOKENS (AÑADIR O MODIFICAR) ---
# =====================================================

class TokenSchema(BaseModel):
    access_token: str
    token_type: str

class TokenPayloadSchema(BaseModel):
    sub: str                    # Subject (identificador de usuario)
    exp: Optional[int] = None   # Expiration time (unix timestamp)
    iat: Optional[int] = None   # Issued at (unix timestamp)
    
    # --- Campos personalizados ---
    token_type: str = "session"
    roles: List[str] = []
    
    # === ¡CAMPOS CRUCIALES! ===
    mfa_enabled: bool = Field(False, description="Indica si el usuario TIENE MFA configurado en la BD")
    mfa_completed: bool = Field(False, description="Indica si para ESTA sesión se pasó el reto MFA")

class PreMFATokenResponseSchema(BaseModel):
    message: str = "MFA verification required."
    pre_mfa_token: str
    username_ad: str

class MFAVerifyRequestSchema(BaseModel):
    username_ad: str
    mfa_code: str
    pre_mfa_token: Optional[str] = None # Mantenemos por si lo quieres añadir en el futuro por seguridad extra

class MFASetupInitiateResponseSchema(BaseModel):
    otpauth_url: str
    message: str = "Scan QR and confirm code."

class MFASetupConfirmRequestSchema(BaseModel):
    mfa_code: str # Coincide con lo que espera tu API de confirmación.

print("SCHEMA_PY_DEBUG: Auth & Token schemas defined.")



# =====================================================
# --- SCHEMAS PARA EL ASISTENTE DE GENERACIÓN DE PROMPTS ---
# =====================================================

# app/schemas/schemas.py
# (Añadir al final del archivo o donde tengas los schemas relacionados con ApiClient)

 

