# app/tools/sql_tools.py (Parte 1: Imports y Prompts)

import json
import traceback
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import quote_plus

# === SQLAlchemy Imports ===
from sqlalchemy import text
from sqlalchemy.sql.expression import TextClause
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

# === LangChain Imports ===
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.language_models.chat_models import BaseChatModel

# === Módulos de la aplicación ===
from app.models.db_connection_config import DatabaseConnectionConfig
from app.utils.security_utils import decrypt_data
from app.schemas.schemas import ParamTransformType

# ==========================================================
# ======>             PLANTILLAS DE PROMPTS            <======
# ==========================================================
TOOL_USAGE_PROMPT_TEMPLATE = (
    "Tu tarea es analizar la PREGUNTA DEL USUARIO y rellenar los valores para los parámetros de la herramienta. Usa lenguaje natural.\n"
    "**Contexto:**\n- DNI del usuario: '{user_dni}'\n"
    "**HERRAMIENTA DISPONIBLE:**\n```json\n{tools_json_str}\n```\n"
    "**HISTORIAL DE CHAT:**\n{chat_history}\n"
    "**PREGUNTA DEL USUARIO:**\n{question}\n\n"
    "**Instrucciones:**\n1. Extrae los valores TAL CUAL los dice el usuario (ej: 'mate 1', 'ciclo actual'). Si un valor no está presente, usa `null`.\n"
    "2. Responde SIEMPRE con un JSON con las claves 'tool_to_use' y 'parameters'.\n\n**Respuesta JSON:**"
)



# En app/tools/sql_tools.py

# Reemplaza la vieja versión con esta:
ANSWER_GENERATION_PROMPT_TEMPLATE = (
    "Eres un asistente experto y amigable. Tu tarea es analizar una pregunta del usuario {user_name} y los datos JSON de la base de datos para darle una respuesta útil.\n\n"
    "Pregunta del Usuario: '{question}'\n"
    "Datos de la Base de Datos:\n"
    "```json\n{db_result_str}\n```\n\n"
    "**Instrucciones:**\n"
    "1.  Responde a la pregunta del usuario usando los datos.\n"
    "2.  Si la pregunta es una simple consulta de notas, preséntalas de forma clara.\n"
    "3.  Si la pregunta es un CÁLCULO SOBRE los datos (ej: '¿cuánto me falta para aprobar?', '¿cuál es mi promedio?'), realiza el cálculo si es posible y explica tu razonamiento.\n"
    "4.  Si el JSON está vacío (`[]`), informa al usuario que no encontraste registros.\n"
    "5.  Habla directamente al usuario en español."
)
# app/tools/sql_tools.py (Parte 2: Funciones Auxiliares)

def _create_async_db_engine(config: DatabaseConnectionConfig) -> AsyncEngine:
    try:
        password = decrypt_data(config.encrypted_password or "")
    except Exception:
        raise ValueError(f"Fallo al desencriptar pwd para la conexión '{config.name}'")

    if config.db_type == 'POSTGRESQL':
        uri = f"postgresql+asyncpg://{config.username}:{quote_plus(password)}@{config.host}:{config.port}/{config.database_name}"
        return create_async_engine(uri)
    raise ValueError(f"Tipo BD '{config.db_type}' no soportado para motor asíncrono.")

async def execute_async_query(engine: AsyncEngine, query: TextClause, params: Optional[Dict[str, Any]] = None) -> str:
    try:
        async with engine.connect() as connection:
            result = await connection.execute(query, params or {})
            rows = [dict(row._mapping) for row in result.fetchall()]
        return json.dumps(rows, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": f"Error al ejecutar consulta: {e}"})

# ========= ¡LA PIEZA CLAVE! EL TRADUCTOR INTELIGENTE =========
async def _step1_extract_from_question(
    question: str, user_dni: Optional[str], chat_history: str, tool_config: Dict[str, Any], llm: BaseChatModel
) -> Dict[str, Any]:
    tool_for_prompt = {k: tool_config.get(k) for k in ("tool_name", "description_for_llm", "parameters")}
    chain = ChatPromptTemplate.from_template(TOOL_USAGE_PROMPT_TEMPLATE) | llm | JsonOutputParser()
    try:
        response = await chain.ainvoke({
            "question": question, "user_dni": user_dni or "No disponible",
            "tools_json_str": json.dumps(tool_for_prompt, indent=2), "chat_history": chat_history
        })
        # Forzamos los parámetros a minúscula para consistencia
        return {k.lower(): v for k, v in response.get("parameters", {}).items()} if isinstance(response, dict) else {}
    except Exception as e:
        print(f"STEP1_EXTRACT_ERROR: {e}")
        return {}

async def _step2_resolve_entities_and_transform(
    params: Dict[str, Any], tool_config: Dict[str, Any], engine: AsyncEngine
) -> Tuple[Dict[str, Any], List[str]]:
    final_params, missing_questions = {}, []
    for p_config in tool_config.get("parameters", []):
        p_name = p_config["name"]
        value = params.get(p_name.lower()) # Buscamos en minúscula

        if value:
            if p_config.get("entity_resolver"):
                entity_type = p_config["entity_resolver"]["entity_type"]
                query = text("SELECT codigo_oficial FROM acad.catalogo_entidades WHERE tipo_entidad = :type AND :term ILIKE ANY(nombres_alias) LIMIT 1")
                resolved_json = await execute_async_query(engine, query, {"type": entity_type.upper(), "term": str(value)})
                try:
                    data = json.loads(resolved_json)
                    if data and "codigo_oficial" in data[0]:
                        original_value, value = value, data[0]["codigo_oficial"]
                        print(f"ENTITY_RESOLVER: Traducido '{original_value}' -> '{value}'")
                except (json.JSONDecodeError, IndexError): pass
            
            value = _apply_transformations(value, p_config.get("transformations", []))
            final_params[p_name] = value

        elif p_config.get("is_required", True):
            missing_questions.append(p_config.get("clarification_question", f"Por favor, proporciona el/la {p_name}."))
            
    return final_params, missing_questions

# app/tools/sql_tools.py (Parte 3: El Orquestador Final)


async def _step3_execute_and_synthesize(
    question: str, params: Dict[str, Any], tool_config: Dict[str, Any], 
    engine: AsyncEngine, llm: BaseChatModel, user_name: Optional[str] # <-- Firma corregida
) -> Dict[str, Any]:
    proc_name = tool_config.get('procedure_name')
    query_str = f"SELECT * FROM {proc_name}({', '.join([f':{p}' for p in params.keys()])})"
    db_result_json = await execute_async_query(engine, text(query_str), params)
    
    ans_chain = ChatPromptTemplate.from_template(ANSWER_GENERATION_PROMPT_TEMPLATE) | llm | StrOutputParser()
    final_answer = await ans_chain.ainvoke({
        "question": question, "db_result_str": db_result_json, "user_name": user_name or "Usuario" # <-- Fallback ultra-genérico
    })
    
    return {"intent": "TOOL_EXECUTED", "final_answer": final_answer, "metadata": {"tool_used": tool_config.get("tool_name"), "procedure_called": proc_name, "parameters_used": params}}

# En app/tools/sql_tools.py


async def run_db_query_chain(
    question: str, chat_history_str: str, db_conn_config: DatabaseConnectionConfig,
    processing_config: Dict[str, Any], llm: BaseChatModel, 
    user_dni: Optional[str] = None,
    user_name: Optional[str] = None, # <-- Recibe el user_name
    partial_params_from_redis: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    
    engine = _create_async_db_engine(db_conn_config)
    tool_config = processing_config.get("tools", [{}])[0]
    if not tool_config: return {"intent": "TOOL_FAILED", "final_answer": "No hay herramientas de BD configuradas."}
    
    # 1. Extracción de la pregunta actual.
    newly_extracted_params = await _step1_extract_from_question(question, user_dni, chat_history_str, tool_config, llm)
    current_params = (partial_params_from_redis or {}).copy()
    current_params.update(newly_extracted_params)
    
    # 2. Traducción y Validación.
    final_params, missing_questions = await _step2_resolve_entities_and_transform(current_params, tool_config, engine)
    
    # 3. Decidir.
    if missing_questions:
        return {"intent": "CLARIFICATION_REQUIRED", "final_answer": missing_questions[0], "metadata": {"partial_parameters": final_params}}
    else:
        # Se pasa el `user_name` al último paso. NO HAY FALLBACKS "hardcodeados" aquí.
        return await _step3_execute_and_synthesize(question, final_params, tool_config, engine, llm, user_name)


