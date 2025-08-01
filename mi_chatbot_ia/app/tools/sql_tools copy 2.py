# app/tools/sql_tools.py 
import asyncio
import re
import json
import traceback
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import quote_plus

# SQLAlchemy Imports
from sqlalchemy import create_engine, Engine
from sqlalchemy.sql import text
from sqlalchemy.sql.expression import TextClause

# LangChain Imports
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.language_models.chat_models import BaseChatModel

# Módulos de la aplicación
from app.models.db_connection_config import DatabaseConnectionConfig
from app.utils.security_utils import decrypt_data
from app.schemas.schemas import ParamTransformType
# Cerca del inicio de app/tools/sql_tools.py, junto a los otros imports de SQLAlchemy

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine


# --- Plantillas con formato seguro y anti-desbordamiento ---

TOOL_USAGE_PROMPT_TEMPLATE = (
    "Eres un asistente de base de datos experto. Tu tarea es analizar la "
    "PREGUNTA DEL USUARIO y determinar si alguna de las HERRAMIENTAS disponibles "
    "puede responderla.\n\n"
    "**Contexto del Usuario:**\n"
    "- DNI del usuario actual (si está disponible): '{user_dni}'\n\n"
    "**HERRAMIENTAS DISPONIBLES (en formato JSON):**\n"
    "```json\n{tools_json_str}\n```\n\n"
    "HISTORIAL DE CHAT (para contexto adicional):\n{chat_history}\n\n"
    "PREGUNTA DEL USUARIO:\n{question}\n\n"
    "Instrucciones de Respuesta:\n"
    "Si una herramienta es adecuada, responde con un único objeto JSON válido que contenga:\n"
    '"tool_to_use": el tool_name exacto de la herramienta elegida.\n'
    '"parameters": un diccionario con los valores para CADA UNO de los parámetros requeridos.\n'
    "Para parámetros como 'dni' o 'documento', DEBES usar el valor del DNI del "
    "usuario actual si está disponible.\n"
    "Si ninguna herramienta es adecuada, responde ÚNICAMENTE con la palabra: NO_TOOL.\n\n"
    "Ejemplo de respuesta JSON si una herramienta aplica:\n"
    "```json\n"
    '{{\n'
    '  "tool_to_use": "fn_app_obtener_notas_curso",\n'
    '  "parameters": {{\n'
    '    "p_ndoc_identidad": "71455461",\n'
    '    "p_scurso": "MATEMATICA I",\n'
    '    "p_speriodo": "2024-1"\n'
    '  }}\n'
    '}}\n'
    "```\n\n"
    "Tu Respuesta (debe ser JSON válido o la palabra NO_TOOL):\n"
)

ANSWER_GENERATION_PROMPT_TEMPLATE = (
    "Tu tarea es actuar como un asistente académico amigable. El usuario preguntó: '{question}'. "
    "Has consultado la base de datos y obtuviste los siguientes datos en formato JSON: \n"
    "--- DATOS DE LA BASE DE DATOS ---\n"
    "{db_result_str}\n"
    "--- FIN DE LOS DATOS ---\n"
    "Basado en los datos, genera una respuesta clara y concisa en ESPAÑOL. "
    "Si hay una 'nota_final', menciónala claramente. Presenta las otras notas como una tabla simple en markdown o una lista. "
    "Si la lista de datos está vacía, informa al usuario que no se encontraron registros para su consulta. "
    "Si hay un error en los datos, comunícalo amablemente. "
    "No inventes información. Comienza la respuesta directamente, sin preámbulos como 'Respuesta Final en Español:'."
)

SQL_GENERATION_BASE_PROMPT_TEMPLATE = (
    "Eres un experto en la generación de consultas SQL. Dada una PREGUNTA, "
    "un ESQUEMA DE TABLAS y un HISTORIAL de chat, escribe una consulta "
    "SQL SELECT correcta para responder la pregunta.\n"
    "Usa ÚNICAMENTE las tablas y columnas del ESQUEMA.\n"
    "Si la pregunta no se puede responder con las tablas provistas, responde "
    "con la palabra NO_SQL_POSSIBLE.\n"
    "Si no se pide un límite de filas, usa LIMIT {{default_limit}}. "
    "NUNCA excedas LIMIT {{max_limit}}.\n\n"
    "ESQUEMA DE TABLAS:\n{{table_info}}\n\n"
    "HISTORIAL DE CHAT:\n{{chat_history}}\n\n"
    "PREGUNTA:\n{{question}}\n\n"
    "Instrucción Final: Responde SOLO con la consulta SQL pura. Sin explicaciones ni markdown.\n"
    "Consulta SQL SELECT Generada:\n"
)

# app/tools/sql_tools.py - [PARTE 2/3: FUNCIONES]

# --- Funciones Auxiliares y Lógica Principal ---

def _apply_transformations(
    value: Any, transformations: List[ParamTransformType]
) -> Any:
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
            match = re.search(r'\d+', current_value)
            if match:
                current_value = match.group(0)
    
    if value != current_value:
      print(f"TRANSFORM: '{value}' -> '{current_value}'")
    return current_value
async def resolve_entity(
    entity_type: str, search_term: str, engine: AsyncEngine
) -> Optional[str]:
    """Busca en el catálogo para encontrar un código oficial, de forma asíncrona."""
    if not search_term or not entity_type: return None

    query = text(
        "SELECT codigo_oficial FROM acad.catalogo_entidades "
        "WHERE tipo_entidad = :entity_type AND :search_term ILIKE ANY(nombres_alias) "
        "LIMIT 1"
    )
    params = {"entity_type": entity_type.upper(), "search_term": search_term}

    # ¡Llamada directa asíncrona! No más asyncio.to_thread
    result_json = await execute_async_query(engine, query, params)
    
    try:
        # Asegúrate de que el resultado no contenga un error de BD
        result_data = json.loads(result_json)
        if isinstance(result_data, dict) and "error" in result_data:
            print(f"ENTITY_RESOLVER: Error en BD al resolver '{search_term}': {result_data['error']}")
            return None # Si hay error, no podemos resolver

        if result_data and isinstance(result_data, list) and "codigo_oficial" in result_data[0]:
            code = result_data[0]["codigo_oficial"]
            print(f"ENTITY_RESOLVER: Encontrado: '{search_term}' -> '{code}'")
            return code
            
    except (json.JSONDecodeError, IndexError, KeyError):
        # Capturamos si el JSON está mal formado, la lista está vacía o falta la clave
        pass # Silenciosamente continuamos si no hay resultado, como antes.

    print(f"ENTITY_RESOLVER: No se encontró código para '{search_term}'.")
    return None

async def run_db_query_chain(
    question: str,
    chat_history_str: str,
    db_conn_config: DatabaseConnectionConfig,
    processing_config: Dict[str, Any],
    llm: BaseChatModel,
    user_dni: Optional[str] = None,
    injected_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Orquestador principal que llama a la cadena de uso de herramientas."""
    tools = processing_config.get("tools", [])
    result = None

    if tools:
        result = await _run_tool_usage_chain(
            question=question, user_dni=user_dni,
            chat_history=chat_history_str, db_conn_config=db_conn_config,
            tools=tools, llm=llm, injected_params=injected_params
        )
    
    if not result:
        return {"intent": "DATABASE_QUERY_FAILED", "final_answer": "Lo siento, no pude procesar tu solicitud."}
        
    if result.get("intent") == "CLARIFICATION_REQUIRED":
        return result
    
    ans_chain = ChatPromptTemplate.from_template(ANSWER_GENERATION_PROMPT_TEMPLATE) | llm | StrOutputParser()
    raw_answer = await ans_chain.ainvoke({
        "question": question, "db_result": result.get("db_result") or "[]"
    })
    
    prefixes_to_clean = ["respuesta final en español:", "respuesta final:", "respuesta:"]
    for prefix in prefixes_to_clean:
        if raw_answer.lower().strip().startswith(prefix):
            raw_answer = raw_answer.strip()[len(prefix):].strip()
            break
    
    return {"intent": result.get("intent"), "final_answer": raw_answer, "metadata": result.get("metadata", {})}
def create_async_db_engine(db_conn_config: DatabaseConnectionConfig) -> AsyncEngine:
    """Crea un motor de SQLAlchemy asíncrono a partir de una configuración."""
    decrypted_password = ""
    if db_conn_config.encrypted_password:
        password_candidate = decrypt_data(db_conn_config.encrypted_password)
        if password_candidate == "[DATO ENCRIPTADO INVÁLIDO]":
            raise ValueError(f"Fallo al desencriptar pwd para '{db_conn_config.name}'")
        decrypted_password = password_candidate

    # ¡Importante! Usamos 'postgresql+asyncpg' para el motor asíncrono
    db_type_str = db_conn_config.db_type.value.lower()
    if db_type_str == "postgresql":
        uri = (f"postgresql+asyncpg://{db_conn_config.username}:"
               f"{quote_plus(decrypted_password)}@{db_conn_config.host}:"
               f"{db_conn_config.port}/{db_conn_config.database_name}")
    else:
        raise ValueError(f"Tipo BD '{db_type_str}' no soportado para motor asíncrono.")

    return create_async_engine(uri)
async def execute_async_query(
    engine: AsyncEngine,
    query: TextClause,
    params: Optional[Dict[str, Any]] = None
) -> str:
    """Ejecuta una consulta de forma asíncrona y devuelve el resultado como JSON string."""
    try:
        async with engine.connect() as connection:
            result_proxy = await connection.execute(query, params or {})
            results = [dict(row._mapping) for row in result_proxy.fetchall()]
        return json.dumps(results, indent=2, default=str)
    except Exception as e:
        error_msg = f"Error al ejecutar la consulta asíncrona: {type(e).__name__} - {e}"
        print(f"SQL_EXEC_ASYNC: {error_msg}")
        traceback.print_exc()  # Es bueno tener el traceback completo mientras depuramos
        return json.dumps({"error": error_msg})
    # Nota: No necesitamos engine.dispose() aquí, la gestión del pool se maneja mejor de forma asíncrona.
async def extract_initial_intention(
    question: str,
    user_dni: Optional[str],
    chat_history: str,
    tools: List[Dict[str, Any]],
    llm: BaseChatModel,
) -> Optional[Dict[str, Any]]:
    """
    Paso 1: EXTRACCIÓN. Usa un LLM para hacer un primer intento de identificar
    la herramienta y los parámetros de la pregunta del usuario.
    No valida, no resuelve, no transforma. Solo extrae.
    """
    if not tools:
        print("INTENTION_EXTRACTOR: No hay herramientas configuradas.")
        return None

    # Preparamos el subset de la configuración de herramientas para el prompt
    tools_for_prompt = [{
        "tool_name": t.get("tool_name"),
        "description": t.get("description_for_llm"),
        "parameters": [
            {
                "name": p.get("name"),
                "type": p.get("type"),
                "is_required": p.get("is_required", True)
            } for p in t.get("parameters", [])
        ]
    } for t in tools]
    
    prompt = ChatPromptTemplate.from_template(TOOL_USAGE_PROMPT_TEMPLATE)
    # Usamos JsonOutputParser para convertir la respuesta del LLM directamente a un diccionario
    chain = prompt | llm | JsonOutputParser()

    try:
        llm_response = await chain.ainvoke({
            "question": question,
            "user_dni": user_dni or "No disponible",
            "tools_json_str": json.dumps(tools_for_prompt, indent=2),
            "chat_history": chat_history
        })

        # Una pequeña validación de la estructura de la respuesta
        if isinstance(llm_response, dict) and "tool_to_use" in llm_response:
            print(f"INTENTION_EXTRACTOR: LLM sugiere usar la herramienta '{llm_response.get('tool_to_use')}'")
            return llm_response
        else:
            # El LLM puede devolver algo que no es un JSON o no tiene la clave esperada
            print(f"INTENTION_EXTRACTOR: La respuesta del LLM no tiene el formato esperado: {llm_response}")
            return None

    except Exception as e:
        print(f"INTENTION_EXTRACTOR: Error crítico parseando la respuesta del LLM: {e}")
        traceback.print_exc()
        return None
# en sql_tools.py
async def fill_parameters_from_user_question(
    user_question: str,
    missing_params: List[Dict[str, Any]], # missing_params es una lista de configs de parámetros
    llm: BaseChatModel
) -> Dict[str, Any]:
    """Usa un LLM para extraer valores para parámetros FALTANTES, dándole contexto."""
    if not missing_params or not user_question:
        return {}

    # Creamos un "esquema" para el LLM, para que entienda qué es cada campo.
    schema_for_llm = [
        {
            "name": p.get("name"),
            "description": p.get("description_for_llm", "un valor para este campo")
        } for p in missing_params
    ]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Eres un experto en extracción de entidades. El usuario está respondiendo a una pregunta "
         "para rellenar un formulario. Necesitas encontrar valores para los siguientes campos basados "
         "en su descripción:\n\n"
         "```json\n{schema}\n```\n\n"
         "Analiza la PREGUNTA DEL USUARIO y extrae los valores. "
         "Responde únicamente con un objeto JSON con las claves y valores que encuentres. "
         "Si un valor no se puede encontrar, no incluyas su clave en el JSON."),
        ("human", "PREGUNTA DEL USUARIO: {question}")
    ])
    
    chain = prompt | llm | JsonOutputParser()
    
    try:
        extracted_data = await chain.ainvoke({
            "schema": json.dumps(schema_for_llm, indent=2, ensure_ascii=False),
            "question": user_question
        })
        if isinstance(extracted_data, dict):
            print(f"PARAM_FILLER (v2): LLM extrajo de la clarificación: {extracted_data}")
            return extracted_data
    except Exception as e:
        print(f"PARAM_FILLER (v2): Error extrayendo de la clarificación. {e}")

    return {}

async def process_and_validate_parameters(
    user_question: str,
    partial_params: Dict[str, Any],
    tool_config: Dict[str, Any],
    engine: AsyncEngine,
    llm: BaseChatModel
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Paso 2: PROCESAR Y VALIDAR. El corazón del bucle de clarificación.
    1. Completa parámetros con la pregunta actual del usuario.
    2. Resuelve entidades (traducción a códigos).
    3. Aplica transformaciones de formato.
    4. Valida qué parámetros requeridos siguen faltando.
    Devuelve (parámetros_listos, parámetros_faltantes_config).
    """
    all_param_configs = tool_config.get("parameters", [])
    current_params = partial_params.copy()

    # --- Rellenar con la pregunta actual ---
    # Primero, identificamos qué nos falta BASADO en lo que ya tenemos
    missing_configs_before_fill = [
        p_cfg for p_cfg in all_param_configs 
        if p_cfg["name"] not in current_params and p_cfg.get("is_required", True)
    ]
    
    if missing_configs_before_fill:
        # Intentamos rellenar los huecos con la pregunta actual del usuario
        newly_extracted_params = await fill_parameters_from_user_question(
            user_question, missing_configs_before_fill, llm
        )
        current_params.update(newly_extracted_params)

    # --- Resolver, Transformar y Validar sobre el conjunto ACTUAL de parámetros ---
    processed_params = {}
    missing_required_configs = []

    for p_cfg in all_param_configs:
        p_name = p_cfg["name"]
        
        # Trabajamos con los parámetros en minúscula para ser consistentes
        value = current_params.get(p_name.lower()) or current_params.get(p_name)

        # 1. Resolución de Entidades
        if value and p_cfg.get("entity_resolver"):
            resolved_code = await resolve_entity(
                entity_type=p_cfg["entity_resolver"]["entity_type"],
                search_term=str(value),
                engine=engine
            )
            if resolved_code:
                value = resolved_code
        
        # 2. Transformaciones
        if value and p_cfg.get("transformations"):
            value = _apply_transformations(value, p_cfg["transformations"])
            
        # 3. Almacenamos el valor procesado o verificamos si falta
        if value is not None and value != "":
            processed_params[p_name] = value
        elif p_cfg.get("is_required", True):
            missing_required_configs.append(p_cfg)
            
    print(f"PARAM_PROCESSOR: Estado final: Parámetros Listos: {list(processed_params.keys())}, Faltantes: {[p['name'] for p in missing_required_configs]}")

    return processed_params, missing_required_configs
async def generate_clarification_question(
    missing_params_configs: List[Dict[str, Any]],
    llm: BaseChatModel
) -> str:
    """
    Paso 3a: GENERAR PREGUNTA. Si faltan parámetros, construye una única
    pregunta de clarificación amigable para el usuario.
    """
    # Caso simple: si solo falta un parámetro, usamos su pregunta predefinida.
    if len(missing_params_configs) == 1:
        param_config = missing_params_configs[0]
        question = param_config.get("clarification_question")
        if question:
            return question
        # Plan B si no hay pregunta de clarificación definida
        return f"Para continuar, necesito que me proporciones el siguiente dato: {param_config.get('name')}."

    # Caso complejo: faltan varios parámetros. Los combinamos con un LLM.
    clarification_prompts = []
    for config in missing_params_configs:
        # Usamos la pregunta de clarificación o, como fallback, el nombre del parámetro.
        prompt_part = config.get("clarification_question", f"un valor para '{config.get('name')}'")
        clarification_prompts.append(f"- {prompt_part}")
        
    questions_str = "\n".join(clarification_prompts)

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Eres un asistente de IA conversacional. Tu tarea es tomar una lista de "
         "preguntas o requerimientos de información y combinarlos en una única "
         "pregunta fluida y amigable para el usuario, en español. "
         "Preséntate como si necesitaras varios datos para poder ayudarle."),
        ("human", 
         "Información que necesito del usuario:\n"
         "{questions_list}\n\n"
         "Tu pregunta combinada y amigable:")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    combined_question = await chain.ainvoke({"questions_list": questions_str})
    
    print(f"CLARIFICATION_GEN: Pregunta generada para el usuario: '{combined_question}'")
    
    return combined_question
async def run_db_query_chain(
    question: str,
    chat_history_str: str,
    db_conn_config: DatabaseConnectionConfig,
    processing_config: Dict[str, Any],
    llm: BaseChatModel,
    user_dni: Optional[str] = None,
    # El estado persistente que viene de Redis. ¡Clave para la memoria!
    partial_params_from_redis: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Orquestador principal que implementa el flujo:
    Extraer -> Procesar/Validar -> (Clarificar O Ejecutar -> Sintetizar)
    """
    partial_params_from_redis = partial_params_from_redis or {}
    
    # Creamos el motor de BD una sola vez y lo pasamos a las funciones
    engine = create_async_db_engine(db_conn_config)
    
    tools = processing_config.get("tools", [])
    if not tools:
        return {"intent": "TOOL_FAILED", "final_answer": "No hay herramientas de base de datos configuradas."}
    
    # Por ahora, asumimos una lógica de una sola herramienta activa a la vez.
    # En el futuro, podríamos tener una selección de herramienta aquí.
    # El `partial_params_from_redis` nos indica si ya estamos en medio de una conversación.
    
    selected_tool_config = tools[0] # Simplificación: Asumimos que la herramienta activa ya se conoce
                                    # Si no hay estado, en el primer turno la selección debería ocurrir
    
    # Si no hay parámetros parciales, hacemos una extracción inicial grande.
    # Si sí los hay, el formulario ya fue "inicializado", por lo que los usamos.
    if not partial_params_from_redis:
        print("ORCHESTRATOR: Turno 1. Extrayendo intención inicial...")
        initial_extraction = await extract_initial_intention(
            question, user_dni, chat_history_str, tools, llm
        )
        if initial_extraction and initial_extraction.get("parameters"):
             # Hacemos el key de los parametros en minusculas
             partial_params_from_redis = {k.lower(): v for k, v in initial_extraction.get("parameters", {}).items()}

    
    # PASO 2: PROCESAR Y VALIDAR (el cerebro)
    # Esta función ahora recibe tanto la info guardada como la nueva pregunta
    # y las fusiona, procesa y valida.
    processed_params, missing_configs = await process_and_validate_parameters(
        user_question=question,
        partial_params=partial_params_from_redis,
        tool_config=selected_tool_config,
        engine=engine,
        llm=llm
    )

    # PASO 3: DECIDIR LA SIGUIENTE ACCIÓN
    if missing_configs:
        # 3.a) ACCIÓN: CLARIFICAR
        print("ORCHESTRATOR: Faltan parámetros. Generando pregunta de clarificación.")
        clarification_q = await generate_clarification_question(missing_configs, llm)
        
        return {
            "intent": "CLARIFICATION_REQUIRED",
            "final_answer": clarification_q,
            "metadata": {
                "tool_name": selected_tool_config.get("tool_name"),
                # MUY IMPORTANTE: Devolvemos los parámetros ya procesados y listos
                # para que se guarden en Redis para el siguiente turno.
                "partial_parameters": processed_params 
            }
        }
    else:
        # 3.b) ACCIÓN: EJECUTAR
        print("ORCHESTRATOR: Parámetros completos. Ejecutando la herramienta en la BD.")
        proc_name = selected_tool_config.get('procedure_name')
        query_obj = text(f"SELECT * FROM {proc_name}({', '.join([f':{p}' for p in processed_params.keys()])})")
        
        db_result_json = await execute_async_query(engine, query_obj, processed_params)
        
        # INICIO DE LA ÚNICA Y CORRECTA LÓGICA DE SÍNTESIS
        try:
            data = json.loads(db_result_json)
            db_result_for_prompt = json.dumps(data, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            db_result_for_prompt = db_result_json
        
        print(f"SYNTHESIS_DEBUG: Resultado de BD PRE-PROCESADO para el prompt: \n{db_result_for_prompt}")
        
        print("ORCHESTRATOR: Sintetizando respuesta final para el usuario.")
        ans_chain = ChatPromptTemplate.from_template(ANSWER_GENERATION_PROMPT_TEMPLATE) | llm | StrOutputParser()
        
        final_answer = await ans_chain.ainvoke({
            "question": question,
            "db_result_str": db_result_for_prompt
        })
        
        print(f"SYNTHIS_DEBUG: Respuesta final generada por el LLM: '{final_answer}'")
        # FIN DE LA LÓGICA DE SÍNTESIS

        return {
            "intent": "TOOL_EXECUTED",
            "final_answer": final_answer, # La variable correcta, que ahora sí sobrevive
            "metadata": {
                "tool_used": selected_tool_config.get("tool_name"),
                "procedure_called": proc_name,
                "parameters_used": processed_params,
                "partial_parameters": None
            }
        }
    
    