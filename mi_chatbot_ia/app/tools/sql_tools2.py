# app/tools/sql_tools.py
import asyncio
import re
import json
import traceback
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import quote_plus

# SQLAlchemy imports
from sqlalchemy import create_engine,  Engine
from sqlalchemy.schema import MetaData, CreateTable
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.language_models.chat_models import BaseChatModel

# Módulos de la aplicación
from app.models.db_connection_config import DatabaseConnectionConfig
from app.utils.security_utils import decrypt_data

# (Asegúrate de tener un get_sync_vector_store en tu app_state)
from app.core.app_state import get_sync_vector_store
from sqlalchemy.sql import text
from sqlalchemy.sql.expression import TextClause
from app.schemas.schemas import ParamTransformType

# --- NUEVAS PLANTILLAS DE PROMPT PARA ARQUITECTURA HÍBRIDA ---
TOOL_USAGE_PROMPT_TEMPLATE = """
Eres un asistente de base de datos experto. Tu tarea es analizar la PREGUNTA DEL USUARIO y determinar si alguna de las HERRAMIENTAS disponibles puede responderla.

**Contexto del Usuario:**
- DNI del usuario actual (si está disponible): '{user_dni}'

**HERRAMIENTAS DISPONIBLES (en formato JSON):**
```json
{tools_json_str}


HISTORIAL DE CHAT (para contexto adicional):
{chat_history}
PREGUNTA DEL USUARIO:
{question}
Instrucciones de Respuesta:
Si una herramienta es adecuada, responde con un único objeto JSON válido que contenga:
"tool_to_use": el tool_name exacto de la herramienta elegida.
"parameters": un diccionario con los valores para CADA UNO de los parámetros requeridos.
Para parámetros como 'dni' o 'documento', DEBES usar el valor del DNI del usuario actual si está disponible.
Si ninguna herramienta es adecuada, responde ÚNICAMENTE con la palabra: NO_TOOL.
Ejemplo de respuesta JSON si una herramienta aplica:
Generated json
{{
"tool_to_use": "fn_app_obtener_notas_curso",
"parameters": {{
    "p_ndoc_identidad": "71455461",
    "p_scurso": "MATEMATICA I",
    "p_speriodo": "2024-1"
}}
}}

Tu Respuesta (debe ser JSON válido o la palabra NO_TOOL):
"""

ANSWER_GENERATION_PROMPT_TEMPLATE = f"""
Dada la PREGUNTA ORIGINAL del usuario y el RESULTADO DE BD obtenido de una consulta o herramienta:
Sintetiza una respuesta final en lenguaje natural, clara y amigable en ESPAÑOL.
Si el RESULTADO DE BD contiene datos (una lista de diccionarios JSON), preséntalos de forma legible (ej. una tabla simple markdown o una lista clara). Si es una lista larga, resume los primeros 5-10 elementos y menciona que hay más resultados.
Si el RESULTADO DE BD es una lista vacía [], informa amablemente que no se encontraron datos para esa consulta.
Si el RESULTADO DE BD contiene un error, indica que hubo un problema técnico al consultar la información.
No inventes información que no esté en el RESULTADO DE BD.
PREGUNTA ORIGINAL: {{question}}
RESULTADO DE BD:

{{db_result}}


Respuesta Final en Español:
"""
SQL_GENERATION_BASE_PROMPT_TEMPLATE = f"""
Eres un experto en la generación de consultas SQL. Dada una PREGUNTA, un ESQUEMA DE TABLAS y un HISTORIAL de chat, escribe una consulta SQL SELECT correcta para responder la pregunta.
Usa ÚNICAMENTE las tablas y columnas del ESQUEMA.
Si la pregunta no se puede responder con las tablas provistas, responde con la palabra NO_SQL_POSSIBLE.
Si no se pide un límite de filas, usa LIMIT {{default_limit}}. NUNCA excedas LIMIT {{max_limit}}.
ESQUEMA DE TABLAS:
{{table_info}}
HISTORIAL DE CHAT:
{{chat_history}}
PREGUNTA:
{{question}}
Instrucción Final: Responde SOLO con la consulta SQL pura. Sin explicaciones ni markdown.
Consulta SQL SELECT Generada:
"""
# --- Fin Plantillas ---

# ============================================
# PARTE 2: FUNCIONES AUXILIARES Y SUB-CADENAS
# Reemplaza todo desde _clean_table_name... hasta justo antes de run_text_to_sql...
# ============================================
def _apply_transformations(value: Any, transformations: List[ParamTransformType]) -> Any:
    """Aplica una lista de transformaciones a un valor de parámetro."""
    if not transformations or not isinstance(value, str):
        return value
    
    current_value = value
    for transform in transformations:
        if transform == ParamTransformType.REMOVE_DASHES:
            current_value = current_value.replace("-", "")
        elif transform == ParamTransformType.TO_UPPER:
            current_value = current_value.upper()
        elif transform == ParamTransformType.EXTRACT_NUMBERS:
            # Extrae la primera secuencia de dígitos que encuentre
            match = re.search(r'\d+', current_value)
            if match:
                current_value = match.group(0)
    
    print(f"TRANSFORM: Valor original '{value}' -> Valor transformado '{current_value}'")
    return current_value

def _get_sync_db_engine(db_conn_config: DatabaseConnectionConfig, context_for_log: str) -> Engine:
    """Crea un motor de SQLAlchemy síncrono a partir de una configuración."""
    # (Tu código para esta función era correcto, lo he mantenido y limpiado)
    print(f"DB_ENGINE_HELPER ({context_for_log}): Creando engine para '{db_conn_config.name}'")
    decrypted_password = ""
    if db_conn_config.encrypted_password:
        password_candidate = decrypt_data(db_conn_config.encrypted_password)
        if password_candidate == "[DATO ENCRIPTADO INVÁLIDO]":
            raise ValueError(f"Fallo al desencriptar pwd para '{db_conn_config.name}'")
        decrypted_password = password_candidate
    
    db_type_str = db_conn_config.db_type.value.lower()
    uri = ""

    if db_type_str == "sqlserver":
        driver = db_conn_config.extra_params.get("driver", "ODBC Driver 17 for SQL Server")
        print(f"DB_ENGINE_HELPER: Usando driver ODBC: '{driver}'")
        driver_encoded = quote_plus(driver)
        uri_base = f"mssql+pyodbc://{db_conn_config.username}:{quote_plus(decrypted_password)}@{db_conn_config.host}"
        if db_conn_config.port: uri_base += f":{db_conn_config.port}"
        uri = f"{uri_base}/{db_conn_config.database_name}?driver={driver_encoded}"
        if str(db_conn_config.extra_params.get("TrustServerCertificate", "")).lower() == "yes":
            uri += "&TrustServerCertificate=yes"
    
    elif db_type_str == "postgresql":
        uri = f"postgresql+psycopg2://{db_conn_config.username}:{quote_plus(decrypted_password)}@{db_conn_config.host}:{db_conn_config.port}/{db_conn_config.database_name}"
    
    else:
        raise ValueError(f"Tipo BD '{db_type_str}' no soportado para engine síncrono.")
    
    if not uri: raise ValueError("No se pudo construir URI de conexión.")
    
    return create_engine(uri)

def _execute_query(db_conn_config: DatabaseConnectionConfig, query: TextClause, params: Optional[Dict[str, Any]] = None) -> str:
    print(f"SQL_EXEC: Ejecutando sobre '{db_conn_config.name}': {str(query)} con params: {params}")
    engine = None
    try:
        engine = _get_sync_db_engine(db_conn_config, context_for_log="QUERY_EXEC")
        with engine.connect() as connection:
            # Ahora la ejecución usa el objeto `text()` y los parámetros por separado
            # Esto permite a SQLAlchemy hacer su magia de forma segura.
            result_proxy = connection.execute(query, params or {}) 
            results = [dict(row._mapping) for row in result_proxy.fetchall()]
        return json.dumps(results, indent=2, default=str)
    except Exception as e:
        error_msg = f"Error al ejecutar la consulta: {type(e).__name__} - {e}"
        print(f"SQL_EXEC: {error_msg}")
        return json.dumps({"error": error_msg})
    finally:
        if engine: engine.dispose()


async def _resolve_entity(entity_type: str, search_term: str, db_conn_config: DatabaseConnectionConfig) -> Optional[str]:
    """Busca en la tabla de catálogos para encontrar el código oficial de una entidad."""
    if not search_term: return None
    print(f"ENTITY_RESOLVER: Buscando '{entity_type}' que coincida con '{search_term}'...")
    
    # Buscamos si el search_term está en el array de nombres_alias
    query = text("""
        SELECT codigo_oficial FROM acad.catalogo_entidades
        WHERE tipo_entidad = :entity_type AND :search_term ILIKE ANY(nombres_alias)
        LIMIT 1
    """)
    params = {"entity_type": entity_type.upper(), "search_term": search_term}
    
    result_json = await asyncio.to_thread(_execute_query, db_conn_config, query, params)
    result_list = json.loads(result_json)
    
    if result_list and "codigo_oficial" in result_list[0]:
        code = result_list[0]["codigo_oficial"]
        print(f"ENTITY_RESOLVER: Encontrado código: '{code}'")
        return code
        
    print(f"ENTITY_RESOLVER: No se encontró código para '{search_term}'.")
    return None



# ... (tus imports y otras funciones auxiliares como _execute_query se mantienen) ...

async def _run_tool_usage_chain(
    question: str, 
    user_dni: Optional[str], 
    chat_history: str, 
    db_conn_config: DatabaseConnectionConfig, 
    tools: List[Dict[str, Any]], 
    llm: BaseChatModel, 
    injected_params: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    
    if not tools: return None
    
    params_from_llm: Dict[str, Any] = {}
    selected_tool_config: Optional[Dict[str, Any]] = None
    
    if injected_params:
        print("SQLTOOLS_TOOL_USAGE: Usando parámetros inyectados, saltando extracción del LLM.")
        selected_tool_config = tools[0] if tools else None
        params_from_llm = injected_params
    else:
        # Lógica de LLM para elegir herramienta y extraer params
        prompt = PromptTemplate.from_template(TOOL_USAGE_PROMPT_TEMPLATE)
        chain = prompt | llm | JsonOutputParser()
        # Aseguramos que los parámetros para el prompt sean listas, no sets.
        tools_for_prompt = [
            {"tool_name": t.get("tool_name"), "description": t.get("description_for_llm"), "parameters": list(t.get("parameters", []))}
            for t in tools
        ]
        
        try:
            llm_response = await chain.ainvoke({"question": question, "user_dni": user_dni or "N/A", "tools_json_str": json.dumps(tools_for_prompt, indent=2), "chat_history": chat_history})
            if not isinstance(llm_response, dict): return None
            
            tool_name = llm_response.get("tool_to_use")
            selected_tool_config = next((t for t in tools if t.get("tool_name") == tool_name), None)
            params_from_llm = {k.lower(): v for k, v in llm_response.get("parameters", {}).items()} if llm_response.get("parameters") else {}
        except Exception as e:
            print(f"SQLTOOLS_TOOL_USAGE: Error parseando respuesta del LLM: {e}")
            return None

    if not selected_tool_config: return None

    # --- FASE DE BÚSQUEDA Y RESOLUCIÓN DE ENTIDADES ---
    print("\n--- FASE DE RESOLUCIÓN DE ENTIDADES ---")
    resolved_params = params_from_llm.copy()
    # --- INICIO DEL NUEVO BLOQUE: FASE DE TRANSFORMACIÓN DE DATOS ---
    print("\n--- FASE DE TRANSFORMACIÓN DE PARÁMETROS ---")
    transformed_params = resolved_params.copy()
    for param_config in selected_tool_config.get("parameters", []):
        param_name = param_config.get("name")
        if param_name in transformed_params:
            transform_list = param_config.get("transformations", [])
            if transform_list:
                transformed_params[param_name] = _apply_transformations(
                    transformed_params[param_name],
                    transform_list
                )

    params_from_llm = transformed_params
    print("--- FIN DE LA FASE DE TRANSFORMACIÓN ---")

    # --- FIN DEL NUEVO BLOQUE ---
    # Mapeo simple de nombre de parámetro a tipo de entidad para el resolver
    param_to_entity_map = {
        "p_scurso": "CURSO",
        "p_speriodo": "PERIODO",
        "p_scarrera": "CARRERA",
    }
    
    for param_name, entity_type in param_to_entity_map.items():
        if param_name in resolved_params and resolved_params[param_name]:
            user_text = resolved_params[param_name]
            resolved_code = await _resolve_entity(entity_type, user_text, db_conn_config)
            if resolved_code:
                resolved_params[param_name] = resolved_code
            else:
                print(f"WARN: No se pudo resolver la entidad '{entity_type}' para el texto '{user_text}'.")
    
    params_from_llm = resolved_params # Actualizamos con los códigos resueltos
    print("--- FIN DE LA FASE DE RESOLUCIÓN ---")

    # --- FASE DE VALIDACIÓN Y EJECUCIÓN ---
    missing_required_params = []
    final_params_for_execution = {}
    for param_config in selected_tool_config.get("parameters", []):
        p_name = param_config.get("name")
        if not p_name: continue
        
        p_required = param_config.get("is_required", True)
        # Usamos .get() para evitar KeyError si un param no se resolvió
        param_value = params_from_llm.get(p_name.lower())
        
        if param_value is not None:
            final_params_for_execution[p_name] = param_value
        elif p_required:
            missing_required_params.append(param_config)
    
    if missing_required_params:
        first_missing = missing_required_params[0]
        clarification_q = first_missing.get("clarification_question") or f"Necesito el dato '{first_missing.get('name')}'."
        return {
            "intent": "CLARIFICATION_REQUIRED",
            "final_answer": clarification_q,
            "metadata": {"missing_parameter_info": first_missing, "partial_parameters": params_from_llm}
        }

    procedure_name = selected_tool_config.get('procedure_name')
    if not procedure_name: return None
    
    query_obj = text(f"SELECT * FROM {procedure_name}({', '.join([f':{p}' for p in final_params_for_execution.keys()])})")
    db_result = await asyncio.to_thread(_execute_query, db_conn_config, query_obj, final_params_for_execution)
    
    return {
        "intent": "TOOL_USED", "db_result": db_result,
        "metadata": {"tool_used": selected_tool_config.get("tool_name"), "procedure_called": procedure_name, "parameters_used": final_params_for_execution}
    }



async def _run_text_to_sql_chain(question: str, chat_history: str, db_conn_config: DatabaseConnectionConfig, processing_config: Dict[str, Any], llm: BaseChatModel) -> Optional[Dict[str, Any]]:
    """Intenta usar el 'Modo Generalista' (Text-to-SQL sobre tablas)."""
    print("SQLTOOLS_GENERALIST: Intentando modo Text-to-SQL...")
    
    tables_to_include = processing_config.get("selected_schema_tables_for_llm", [])
    if not tables_to_include:
        print("SQLTOOLS_GENERALIST: No hay tablas seleccionadas para este modo.")
        return None
    
    # Esta parte asume que el DDL de las tablas está en el Vector Store (como lo teníamos antes).
    # Este es el paso de RAG sobre el schema de la BD.
    vector_store = get_sync_vector_store()
    retriever = vector_store.as_retriever(search_kwargs={"filter": {"db_connection_name": db_conn_config.name}})
    
    schema_docs = await asyncio.to_thread(retriever.get_relevant_documents, f"{question} Tablas: {','.join(tables_to_include)}")
    table_info = "\n\n".join([doc.page_content for doc in schema_docs])
    if not table_info:
        print("SQLTOOLS_GENERALIST: No se encontró schema en Vector Store.")
        return None
    
    sql_policy = processing_config.get("sql_select_policy", {})
    prompt_template = PromptTemplate.from_template(
        SQL_GENERATION_BASE_PROMPT_TEMPLATE.format(
            default_limit=sql_policy.get('default_select_limit', 10),
            max_limit=sql_policy.get('max_select_limit', 100),
            table_info="{table_info}", question="{question}", chat_history="{chat_history}"
        )
    )

    sql_chain = prompt_template | llm | StrOutputParser()
    generated_sql = await sql_chain.ainvoke({"question": question, "chat_history": chat_history, "table_info": table_info})
    
    if "NO_SQL_POSSIBLE" in generated_sql:
        return {"intent": "TEXT_TO_SQL_REJECTED", "db_result": "No fue posible generar una consulta SQL.", "metadata": {}}
    
    db_result = await asyncio.to_thread(_execute_query, db_conn_config, generated_sql)
    
    return {
        "intent": "TEXT_TO_SQL_GENERATED", "db_result": db_result, "metadata": {"generated_sql": generated_sql}
    }

# ============================================
# PARTE 3: FUNCIÓN ORQUESTADORA PRINCIPAL
# Pega esto al final de tu archivo sql_tools.py
# ============================================

# app/tools/sql_tools.py

async def run_db_query_chain(
    question: str,
    chat_history_str: str,
    db_conn_config: DatabaseConnectionConfig,
    processing_config: Dict[str, Any],
    llm: BaseChatModel,
    user_dni: Optional[str] = None,
    injected_params: Optional[Dict[str, Any]] = None # <--- PARÁMETRO AÑADIDO
) -> Dict[str, Any]:
    
    result: Optional[Dict[str, Any]] = None
    tools = processing_config.get("tools", [])

    # El flujo con inyección solo aplica si hay herramientas
    if tools:
        print("SQLTOOLS_ORCHESTRATOR: Hay herramientas definidas, intentando usarlas...")
        result = await _run_tool_usage_chain(
            question=question,
            user_dni=user_dni,
            chat_history=chat_history_str,
            db_conn_config=db_conn_config,
            tools=tools,
            llm=llm,
            injected_params=injected_params # <-- LO PASAMOS AQUÍ
        )
    
    if not result:
        print("SQLTOOLS_ORCHESTRATOR: No se usó/pudo usar herramienta. Intentando modo generalista.")
        result = await _run_text_to_sql_chain(
            question=question,
            chat_history=chat_history_str,
            db_conn_config=db_conn_config,
            processing_config=processing_config,
            llm=llm
        )

    if not result: # Fallback final
        return {"intent": "DATABASE_QUERY_FAILED", "final_answer": "Lo siento, no pude procesar tu solicitud...", "metadata": {}}
        
    if result.get("intent") == "CLARIFICATION_REQUIRED":
        return result
    
    answer_prompt = ChatPromptTemplate.from_template(ANSWER_GENERATION_PROMPT_TEMPLATE)
    answer_chain = answer_prompt | llm | StrOutputParser()
    
    llm_output_raw = await answer_chain.ainvoke({"question": question, "chat_history": chat_history_str, "db_result": result.get("db_result") or "[]"})
    
    # Limpieza de respuesta final
    final_answer = llm_output_raw
    for prefix in ["respuesta final en español:", "respuesta final:", "respuesta:"]:
        if final_answer.lower().strip().startswith(prefix):
            final_answer = final_answer.strip()[len(prefix):].strip()
            break
    
    return {"intent": result.get("intent"), "final_answer": final_answer, "metadata": result.get("metadata", {})}