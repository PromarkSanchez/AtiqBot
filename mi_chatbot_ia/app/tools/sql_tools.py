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

 
ANSWER_GENERATION_PROMPT_TEMPLATE = (
    "## ROL Y OBJETIVO\n"
    "Eres un asistente académico amigable y eficiente llamado Hered-IA. Te diriges al usuario por su nombre, {user_name}.\n"
    "Tu única tarea es tomar los datos JSON que provienen de la base de datos y presentarlos al usuario de forma natural, clara y conversacional en español. NUNCA menciones la palabra 'JSON' ni 'base de datos'.\n\n"
    "## DATOS RECIBIDOS\n"
    "La pregunta del usuario fue: '{question}'\n"
    "Los datos obtenidos son:\n"
    "```json\n{db_result_str}\n```\n\n"
    "## INSTRUCCIONES DE RESPUESTA\n"
    "1.  **Si los datos NO están vacíos:** Presenta la información como en el EJEMPLO DE SALIDA. Resume primero la nota final y luego detalla las notas parciales en una lista o tabla simple.\n"
    "2.  **Si los datos están vacíos (`[]`):** Responde amablemente que no encontraste información, como: 'Hola, {user_name}. Busqué en el sistema, pero no encontré registros de notas para esa consulta. ¿Podrías verificar los datos del curso o ciclo?'\n"
    "3.  **Si la pregunta es un cálculo:** Usa los datos para responder a la pregunta. Por ejemplo, si te preguntan '¿cuánto me falta para 20?', calcula la diferencia.\n\n"
    "## EJEMPLO DE CÓMO PROCESAR LOS DATOS\n"
    "### Si recibes este JSON:\n"
    "```json\n"
    "[\n"
    "  {{\n"    # <--- ¡CORRECCIÓN! Doble llave de apertura
    "    \"tipo_nota\": \"Desempeño\",\n"
    "    \"ponderacion\": \"70.00%\",\n"
    "    \"nota\": 18.25,\n"
    "    \"nota_final\": 16.79\n"
    "  }},\n"   # <--- ¡CORRECCIÓN! Doble llave de cierre
    "  {{\n"    # <--- ¡CORRECCIÓN!
    "    \"tipo_nota\": \"Práctica Clínica\",\n"
    "    \"ponderacion\": \"75.00%\",\n"
    "    \"nota\": 18.00,\n"
    "    \"nota_final\": 16.79\n"
    "  }}\n"   # <--- ¡CORRECCIÓN!
    "]\n"
    "```\n"
    # El {user_name} en la respuesta de ejemplo también necesita escaparse
    "### Tu respuesta debería ser algo como esto:\n"
    "¡Claro, {{user_name}}! Aquí tienes el detalle de tus notas para el curso.\n\n" # <--- ¡CORRECCIÓN!
    "Tu nota final es de **16.79**.\n\n"
    "El desglose es el siguiente:\n"
    "- **Desempeño:** 18.25 (Ponderación: 70.00%)\n"
    "- **Práctica Clínica:** 18.00 (Ponderación: 75.00%)\n"
    "...\n\n"
    "¡Felicidades por aprobar el curso! Si necesitas ayuda con algún cálculo o tienes otra duda, avísame. 🚀\n"
    "--- (Fin del ejemplo) ---\n\n"
    "**Tu Respuesta (Dirigida a {user_name}):**"
)
# app/tools/sql_tools.py (Parte 2: Funciones Auxiliares)
def _apply_transformations(value: Any, transformations: List[Dict[str, Any]]) -> Any:
    if not transformations:
        return value
    
    new_value = str(value)
    for transform in transformations:
        t_type = transform.get("type", "").upper()
        if t_type == "STRIP":
            new_value = new_value.strip()
        elif t_type == "UPPERCASE":
            new_value = new_value.upper()
        elif t_type == "LOWERCASE":
            new_value = new_value.lower()
        elif t_type == "REMOVE_DASHES":
            new_value = new_value.replace("-", "")
    return new_value


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
    params: Dict[str, Any], 
    tool_config: Dict[str, Any], 
    engine: AsyncEngine,
    user_dni: Optional[str]
) -> Tuple[Dict[str, Any], List[str]]:
    
    final_params, missing_questions = {}, []
    
    for p_config in tool_config.get("parameters", []):
        p_name = p_config["name"]
        value = params.get(p_name.lower())

        if p_config.get("is_dni_param") and user_dni:
            print(f"DNI_HANDLER: Parámetro '{p_name}' identificado como DNI. Usando '{user_dni}' del usuario.")
            value = user_dni

        if value:
            value = _apply_transformations(value, p_config.get("transformations", []))

            if p_config.get("entity_resolver"):
                entity_type = p_config["entity_resolver"]["entity_type"]
                
                # --- ¡LA CONSULTA MEJORADA Y MÁS FLEXIBLE! ---
                # Esta consulta ahora busca si el término del usuario contiene alguno de los alias.
                # Ejemplo: Si el usuario dice "estudio medicina" y un alias es "medicina", ¡encontrará una coincidencia!
                query_str = """
                SELECT codigo_oficial FROM acad.catalogo_entidades
                WHERE tipo_entidad = :type
                AND (
                    :term ILIKE ANY(nombres_alias) OR
                    EXISTS (
                        SELECT 1
                        FROM unnest(nombres_alias) AS alias
                        WHERE :term ILIKE '%' || alias || '%'
                    )
                )
                LIMIT 1;
                """
                query = text(query_str)
                # La búsqueda se hará contra el `tipo_entidad` en mayúsculas para consistencia
                resolved_json = await execute_async_query(engine, query, {"type": entity_type.upper(), "term": str(value)})

                try:
                    data = json.loads(resolved_json)
                    if data and "codigo_oficial" in data[0]:
                        original_value, value = value, data[0]["codigo_oficial"]
                        print(f"ENTITY_RESOLVER: Traducido '{original_value}' -> '{value}'")
                    else:
                        # Si no encontramos una traducción, es mejor registrarlo como una advertencia
                        print(f"ENTITY_RESOLVER_WARN: No se pudo resolver '{value}' para el tipo '{entity_type}'. Usando valor original.")
                except (json.JSONDecodeError, IndexError):
                    print(f"ENTITY_RESOLVER_WARN: Error de JSON o índice al resolver '{value}'. Usando valor original.")

            final_params[p_name] = value

        elif p_config.get("is_required", True):
            missing_questions.append(p_config.get("clarification_question", f"Por favor, proporciona el/la {p_name}."))
            
    return final_params, missing_questions

# app/tools/sql_tools.py (Parte 3: El Orquestador Final)


async def _step3_execute_and_synthesize(
    question: str, 
    params: Dict[str, Any], 
    tool_config: Dict[str, Any], 
    engine: AsyncEngine, 
    llm: BaseChatModel, 
    user_name: Optional[str]
) -> Dict[str, Any]:
    
    proc_name = tool_config.get('procedure_name')
    
    # --- ¡CAMBIO CLAVE! AHORA ORDENAMOS LOS PARÁMETROS ---
    
    # 1. Obtenemos el orden correcto desde la configuración de la herramienta
    param_order = [p["name"] for p in tool_config.get("parameters", [])]
    
    # 2. Creamos una lista de los valores de los parámetros EN ESE ORDEN
    # Usamos .get(p_name) para evitar errores si un param no se encontró (aunque no debería pasar aquí)
    param_values = [params.get(p_name) for p_name in param_order]
    
    # 3. Creamos placeholders posicionales anónimos (ej: :param_1, :param_2)
    positional_placeholders = [f':param_{i+1}' for i in range(len(param_order))]
    
    # 4. Construimos la consulta y el diccionario de valores para SQLAlchemy
    query_str = f"SELECT * FROM {proc_name}({', '.join(positional_placeholders)})"
    query_params = {f'param_{i+1}': val for i, val in enumerate(param_values)}
    
    print(f"SQL_EXEC: Llamando a '{proc_name}' con parámetros en orden: {param_order} y valores: {query_params}")
    
    db_result_json = await execute_async_query(engine, text(query_str), query_params)
    
    ans_chain = ChatPromptTemplate.from_template(ANSWER_GENERATION_PROMPT_TEMPLATE) | llm | StrOutputParser()
    final_answer = await ans_chain.ainvoke({
        "question": question, 
        "db_result_str": db_result_json, 
        "user_name": user_name or "Usuario"
    })
    
    # En el metadata, seguimos mostrando los nombres lógicos para que sea legible
    return {"intent": "TOOL_EXECUTED", "final_answer": final_answer, "metadata": {"tool_used": tool_config.get("tool_name"), "procedure_called": proc_name, "parameters_used": params}}
# En app/tools/sql_tools.py


async def run_db_query_chain(
    question: str, chat_history_str: str, db_conn_config: DatabaseConnectionConfig,
    processing_config: Dict[str, Any], llm: BaseChatModel, 
    user_dni: Optional[str] = None,
    user_name: Optional[str] = None,
    partial_params_from_redis: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    
    engine = _create_async_db_engine(db_conn_config)
    tool_config = processing_config.get("tools", [{}])[0]
    if not tool_config: return {"intent": "TOOL_FAILED", "final_answer": "No hay herramientas de BD configuradas."}
    
    # 1. Extraemos SOLO los parámetros de la pregunta actual
    newly_extracted_params = await _step1_extract_from_question(
        question, user_dni, chat_history_str, tool_config, llm
    )
    
    # 2. Combinamos inteligentemente los parámetros: los nuevos tienen prioridad
    # sobre los guardados en Redis.
    combined_params_before_transform = (partial_params_from_redis or {}).copy()
    combined_params_before_transform.update(newly_extracted_params)
    
    # --- ¡CAMBIO ESTRUCTURAL CLAVE! ---
    # 3. AHORA aplicamos la resolución y transformación al CONJUNTO COMPLETO
    # de parámetros combinados, no solo a los nuevos.
    final_params, missing_questions = await _step2_resolve_entities_and_transform(
        params=combined_params_before_transform, 
        tool_config=tool_config, 
        engine=engine, 
        user_dni=user_dni
    )
    
    # 4. Decidir el siguiente paso
    if missing_questions:
        final_params_to_save = {k: v for k, v in final_params.items() if v is not None and v != ""}
        # Guardamos en Redis los parámetros YA PROCESADOS (transformados y resueltos) que tenemos
        return {
            "intent": "CLARIFICATION_REQUIRED",
            "final_answer": missing_questions[0],
            "metadata": {"partial_parameters": final_params_to_save}
        }
    else:
        # Al tener todos los parámetros, ejecutamos el final
        return await _step3_execute_and_synthesize(
            question, final_params, tool_config, engine, llm, user_name
        )


