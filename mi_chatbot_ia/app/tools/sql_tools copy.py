# app/tools/sql_tools.py
import asyncio
import re # <--- ¡AÑADIDO IMPORT RE!
import traceback
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import quote_plus

# SQLAlchemy imports
from sqlalchemy import create_engine, MetaData # type: ignore
from sqlalchemy.schema import CreateTable  # type: ignore
from sqlalchemy.engine import Engine  # type: ignore

# Langchain imports
from langchain_community.utilities import SQLDatabase # type: ignore
from langchain_google_genai import ChatGoogleGenerativeAI # O el tipo base si usas varios LLMs # type: ignore
from langchain_core.prompts import PromptTemplate # type: ignore
from langchain_core.runnables import RunnablePassthrough # type: ignore
from langchain_core.output_parsers import StrOutputParser # type: ignore

# Modelos de la aplicación
from app.models.db_connection_config import DatabaseConnectionConfig 
from app.utils.security_utils import decrypt_data 

# --- Plantillas de Prompt (sin cambios) ---
SQL_GENERATION_BASE_PROMPT_TEMPLATE = """Eres un experto en SQL Server T-SQL. Dada una PREGUNTA DEL USUARIO, un HISTORIAL DE CHAT opcional, y un ESQUEMA DE TABLAS relevantes, escribe una consulta SQL SELECT semánticamente correcta para responder la pregunta.

**Reglas Estrictas para la Consulta SQL:**
1.  SOLO genera consultas SQL SELECT. NO uses INSERT, UPDATE, DELETE, DROP, etc.
2.  Si no se especifica un límite de filas en la pregunta, AÑADE '{default_top_clause}' a la consulta (ej. 'TOP {default_limit}'). No excedas NUNCA el límite de 'TOP {max_limit}'.
3.  USA ÚNICAMENTE las tablas y columnas proporcionadas en el ESQUEMA DE TABLAS. No inventes tablas o columnas. Los nombres de tablas y columnas en el esquema proporcionado son los correctos. Para SQL Server, si se provee esquema, usa la forma Esquema.Tabla o [Esquema].[Tabla] en tu consulta (prefiere Esquema.Tabla si no hay espacios ni caracteres especiales).
4.  Si la pregunta pide operaciones no permitidas, información fuera del esquema provisto, o si es imposible generar una consulta válida, responde únicamente con la palabra: "NO_SQL_POSSIBLE".
{custom_llm_instructions_str}

**ESQUEMA DE TABLAS RELEVANTES (DDL y/o descripciones adicionales provistas por el usuario):**
{table_info}

**HISTORIAL DE CHAT (si aplica y es relevante para desambiguar la pregunta actual):**
{chat_history}

**PREGUNTA DEL USUARIO (para generar SQL):**
{question}

**Instrucción Final de Formato: Responde ÚNICA Y EXCLUSIVAMENTE con la consulta SQL SELECT. No incluyas explicaciones, saludos, ni formato markdown como ```sql. Solo la consulta SQL pura.**

Consulta SQL SELECT Generada:
""" # <-- Añadí la instrucción explícita para formato

ANSWER_GENERATION_BASE_PROMPT_TEMPLATE = """Dada la PREGUNTA ORIGINAL del usuario, la CONSULTA SQL generada, el RESULTADO DE BD obtenido y un HISTORIAL DE CHAT opcional:
Sintetiza una respuesta final en lenguaje natural y en ESPAÑOL para el usuario.
Si la CONSULTA SQL fue "NO_SQL_POSSIBLE" o si el RESULTADO DE BD está vacío, o si indica un error o "No se pudo generar una consulta SQL", informa amablemente al usuario que no se pudo obtener la información específica solicitada de la base de datos, y si es posible, explica brevemente por qué (ej. "la pregunta es muy ambigua" o "no hay datos para esos criterios" o "la información solicitada no está disponible en las tablas permitidas").
No inventes información que no esté en el RESULTADO DE BD. Sé conciso y directo. Si el resultado es una lista grande, resume los puntos clave o las primeras filas.

PREGUNTA ORIGINAL: {question}
HISTORIAL DE CHAT: {chat_history}
CONSULTA SQL GENERADA: {sql_query}
RESULTADO DE BD: {sql_result}

Respuesta Final en Español:
"""
# --- Fin Plantillas ---

def _clean_table_name_for_reflection(qualified_table_name: str) -> Tuple[Optional[str], str]:
    name_no_brackets = qualified_table_name.replace("[", "").replace("]", "")
    if "." in name_no_brackets:
        schema, table = name_no_brackets.split(".", 1)
        return schema.strip(), table.strip()
    return None, name_no_brackets.strip()

def _get_sync_db_engine(db_conn_config: DatabaseConnectionConfig, context_for_log: str) -> Engine:
    print(f"DB_ENGINE_HELPER ({context_for_log}): Creando engine para '{db_conn_config.name}'")
    decrypted_password = ""
    if db_conn_config.encrypted_password:
        password_candidate = decrypt_data(db_conn_config.encrypted_password)
        if password_candidate == "[DATO ENCRIPTADO INVÁLIDO]":
            raise ValueError(f"DB_ENGINE_HELPER ({context_for_log}): No se pudo desencriptar pwd para '{db_conn_config.name}'")
        decrypted_password = password_candidate
    
    db_type_str = db_conn_config.db_type.value.lower()
    uri = ""

    if db_type_str == "sqlserver":
        driver = "{ODBC Driver 18 for SQL Server}" 
        if db_conn_config.extra_params and isinstance(db_conn_config.extra_params, dict):
            driver_from_config = db_conn_config.extra_params.get("driver")
            if driver_from_config and isinstance(driver_from_config, str):
                driver = driver_from_config
        
        driver_name_cleaned = driver.strip('{}')
        driver_encoded = quote_plus(driver_name_cleaned)
        
        uri_base = (f"mssql+pyodbc://{db_conn_config.username}:{quote_plus(decrypted_password)}@{db_conn_config.host}")
        if db_conn_config.port:
            uri_base += f":{db_conn_config.port}"
        uri = f"{uri_base}/{db_conn_config.database_name}?driver={driver_encoded}"
        
        if db_conn_config.extra_params and isinstance(db_conn_config.extra_params, dict):
            if str(db_conn_config.extra_params.get("TrustServerCertificate", "")).lower() == "yes":
                uri += "&TrustServerCertificate=yes"
                uri += "&Encrypt=no"

    elif db_type_str == "postgresql":
        uri = f"postgresql+psycopg2://{db_conn_config.username}:{quote_plus(decrypted_password)}@{db_conn_config.host}:{db_conn_config.port}/{db_conn_config.database_name}"
    else:
        raise ValueError(f"DB_ENGINE_HELPER ({context_for_log}): Tipo BD '{db_type_str}' no soportado para engine síncrono.")
    
    if not uri:
        raise ValueError(f"DB_ENGINE_HELPER ({context_for_log}): No se pudo construir URI.")
    
    return create_engine(uri)


def create_langchain_sql_db_for_execution_only(
    db_conn_config: DatabaseConnectionConfig
) -> SQLDatabase:
    db_engine = _get_sync_db_engine(db_conn_config, context_for_log="SQLDB_EXEC")
    sql_db_instance = SQLDatabase(engine=db_engine, sample_rows_in_table_info=0)
    print(f"SQLTOOLS_SQLDB_EXEC: SQLDatabase (para ejecución) creada. Dialecto: {sql_db_instance.dialect}")
    return sql_db_instance


def generate_ddl_for_tables_directly(
    db_conn_config: DatabaseConnectionConfig,
    tables_to_include: List[str]
) -> str:
    print("\n--- Entrando en generate_ddl_for_tables_directly ---")
    
    
    print(f"DDL_GEN: Iniciando para conexión '{db_conn_config.name}', tablas: {tables_to_include}")
    if not tables_to_include:
        print("DDL_GEN: No hay tablas especificadas para generar DDL.")
        return "/* No se especificaron tablas para obtener su esquema. */"

    ddl_engine: Optional[Engine] = None
    try:
        ddl_engine = _get_sync_db_engine(db_conn_config, context_for_log="DDL_GEN")
        print("DDL_GEN: Engine creado. A punto de iniciar reflexión de metadatos...")
        ddl_statements: List[str] = []
        schemas_to_reflect_map: Dict[str, List[str]] = {}
        print("DDL_GEN: Reflexión de metadatos completada.")

        for qualified_name in tables_to_include:
            schema, table_name_only = _clean_table_name_for_reflection(qualified_name)
            if schema: 
                if schema not in schemas_to_reflect_map:
                    schemas_to_reflect_map[schema] = []
                schemas_to_reflect_map[schema].append(table_name_only)
            else:
                print(f"DDL_GEN: ADVERTENCIA - Tabla '{qualified_name}' no tiene esquema explícito. Será ignorada.")

        for schema_name, table_list_in_schema in schemas_to_reflect_map.items():
            try:
                print(f"DDL_GEN: Reflejando desde esquema '{schema_name}' las tablas: {table_list_in_schema}")
                current_schema_metadata = MetaData()
                current_schema_metadata.reflect(bind=ddl_engine, only=table_list_in_schema, schema=schema_name)
                
                generated_count_for_schema = 0
                for table_reflected_key in current_schema_metadata.tables:
                    table_object = current_schema_metadata.tables[table_reflected_key]
                    ddl_create_table = str(CreateTable(table_object).compile(ddl_engine)).strip()
                    ddl_statements.append(f"-- DDL para tabla: {table_object.fullname}\n{ddl_create_table};")
                    generated_count_for_schema +=1
                print(f"DDL_GEN: DDL generado para {generated_count_for_schema} tablas en '{schema_name}'.")
            except Exception as e_reflect_ddl:
                print(f"DDL_GEN: Error al reflejar/generar DDL para tablas en '{schema_name}': {e_reflect_ddl}")
                traceback.print_exc()
        
        if not ddl_statements:
            return "No se pudo generar el DDL para las tablas especificadas. Verifica nombres, esquemas, permisos y logs."
        return "\n\n".join(ddl_statements)
    finally:
        if ddl_engine:
            ddl_engine.dispose()
            print(f"DDL_GEN: Engine para DDL dispuesto para '{db_conn_config.name}'.")

def _validate_generated_sql(sql_query: str, policy: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    sql_query_upper = sql_query.strip().upper() # `sql_query` ya debería ser el SQL puro aquí
    
    if not sql_query_upper:
        return False, "La consulta SQL generada está vacía."
    if sql_query_upper == "NO_SQL_POSSIBLE":
        print("SQL_VALIDATE: LLM indicó NO_SQL_POSSIBLE. Se considera válido en el flujo.")
        return True, None
    if not sql_query_upper.startswith("SELECT"):
        msg = "La consulta generada no es un SELECT."
        print(f"SQL_VALIDATE: {msg} (Recibido: '{sql_query[:30]}...')") # Log extra
        return False, msg

    disallowed_constructs = policy.get("disallowed_sql_constructs", [])
    if isinstance(disallowed_constructs, list):
        for construct in disallowed_constructs:
            if isinstance(construct, str) and construct.strip().upper() in sql_query_upper:
                msg = f"La consulta generada contiene una construcción no permitida: '{construct}'."
                print(f"SQL_VALIDATE: {msg}")
                return False, msg
    
    print(f"SQL_VALIDATE: SQL '{sql_query_upper[:100]}...' parece válido según política básica.")
    return True, None

def execute_sql_query_with_db_instance(query: str, db_instance: SQLDatabase) -> str:
    print(f"SQL_EXECUTE: Intentando ejecutar query: {query[:200]}...")
    try:
        result = db_instance.run(query) # `query` ya es el SQL puro
        result_str = str(result)
        print(f"SQL_EXECUTE: Resultado obtenido (primeros 300 chars): {result_str[:300]}...")
        return result_str
    except Exception as e:
        error_msg = f"Error al ejecutar la consulta en la base de datos: {type(e).__name__} - {e}"
        print(f"SQL_EXECUTE: {error_msg} para query: '{query}'")
        # traceback.print_exc() # Descomentar para debug detallado de errores SQL
        return error_msg

async def run_text_to_sql_lcel_chain(
    question: str,
    chat_history_str: str,
    db_conn_config_for_sql: DatabaseConnectionConfig,
    llm: ChatGoogleGenerativeAI,
    sql_policy: Dict[str, Any]
) -> Dict[str, Any]:
        # <<<--- AÑADE ESTOS PRINTS DE DEBUG ---
    print("\n" + "*"*50)
    print("DEBUG SQL_TOOLS: `sql_policy` recibido en la función:")
    print(f"Tipo de dato: {type(sql_policy)}")
    import json; print(f"Contenido JSON: {json.dumps(sql_policy, indent=2)}")
    print("*"*50 + "\n")
    # --- FIN DE PRINTS DE DEBUG ---
    print("SQLTOOLS_RUN_CHAIN: === Iniciando Text-to-SQL LCEL (con DDL manual) ===")
    
    #tables_from_policy = sql_policy.get("allowed_tables_for_select", [])
    tables_from_policy = sql_policy.get("sql_select_policy", {}).get("allowed_tables_for_select", [])

    if not isinstance(tables_from_policy, list) or not all(isinstance(t, str) for t in tables_from_policy):
        print("SQLTOOLS_RUN_CHAIN: ADVERTENCIA - `allowed_tables_for_select` es inválido. Se usará lista vacía.")
        tables_from_policy = []
    print(f"SQLTOOLS_RUN_CHAIN: Tablas permitidas (de política): {tables_from_policy}")

    default_error_response = {
        "generated_sql": "ERROR_PRE_PROCESSING",
        "db_query_result": "No se pudo iniciar el proceso Text-to-SQL.",
        "final_answer_llm": "Hubo un problema interno al intentar preparar la consulta a la base de datos."
    }

    try:
        langchain_sql_db_for_execution = create_langchain_sql_db_for_execution_only(db_conn_config_for_sql)
    except Exception as e_sql_db_create:
        print(f"SQLTOOLS_RUN_CHAIN: ERROR CRÍTICO al crear SQLDatabase: {e_sql_db_create}")
        traceback.print_exc()
        default_error_response["db_query_result"] = f"Error creando conexión a BD: {e_sql_db_create}"
        default_error_response["final_answer_llm"] = "No se pudo establecer la conexión con la BD para ejecutar consultas."
        return default_error_response
        
    table_info_for_llm_prompt_str: str
    if not tables_from_policy:
        table_info_for_llm_prompt_str = "/* No se han especificado tablas permitidas para esta consulta en la política de contexto. */"
        print("SQLTOOLS_RUN_CHAIN: ADVERTENCIA - No hay `allowed_tables_for_select`. El LLM no tendrá esquema.")
    else:
        print(f"SQLTOOLS_RUN_CHAIN: Generando DDL para tablas: {tables_from_policy}...")
        try:
            table_info_for_llm_prompt_str = await asyncio.to_thread(
                generate_ddl_for_tables_directly, db_conn_config_for_sql, tables_from_policy
            )
        except Exception as e_ddl_gen:
            print(f"SQLTOOLS_RUN_CHAIN: ERROR al generar DDL: {e_ddl_gen}")
            traceback.print_exc()
            return {
                "generated_sql": "ERROR_DDL_GENERATION",
                "db_query_result": f"Fallo en generación de DDL: {e_ddl_gen}",
                "final_answer_llm": "No pude obtener la info del esquema de la BD necesaria (error interno)."
            }

    print(f"SQLTOOLS_RUN_CHAIN: DDL que se pasará al LLM (primeros 500 chars):\n{table_info_for_llm_prompt_str[:500]}...")
    
    is_ddl_problematic = (
        "No se pudo generar el DDL" in table_info_for_llm_prompt_str or
        "No se especificaron tablas" in table_info_for_llm_prompt_str or
        not table_info_for_llm_prompt_str.strip() or
        table_info_for_llm_prompt_str.strip() == "/* */"
    )
    if is_ddl_problematic and "/* No se han especificado tablas permitidas" not in table_info_for_llm_prompt_str:
        print(f"SQLTOOLS_RUN_CHAIN: DDL problemático: '{table_info_for_llm_prompt_str[:100]}...'. Abortando.")
        return {
            "generated_sql": "ERROR_DDL_INVALID_OR_EMPTY",
            "db_query_result": table_info_for_llm_prompt_str,
            "final_answer_llm": "No se pudo obtener un esquema de BD válido para procesar tu pregunta."
        }

    default_limit = sql_policy.get("default_select_limit", 10)
    max_limit = sql_policy.get("max_select_limit", 100)
    
    db_dialect_lower = langchain_sql_db_for_execution.dialect.lower()
    default_top_clause_str = ""
    if db_dialect_lower in ["tsql", "mssql"]:
        default_top_clause_str = f"TOP {default_limit}"
    elif db_dialect_lower == "postgresql":
        default_top_clause_str = f"LIMIT {default_limit}"
    else:
        print(f"SQLTOOLS_RUN_CHAIN: Dialecto '{db_dialect_lower}' sin cláusula default TOP/LIMIT configurada.")

    custom_llm_instr_list = sql_policy.get("llm_instructions_for_select", [])
    custom_llm_instr_str_for_prompt = ""
    if isinstance(custom_llm_instr_list, list) and custom_llm_instr_list:
         custom_llm_instr_str_for_prompt = "\nInstrucciones Adicionales para SQL:\n" + "\n".join(
            [f"- {instr}" for instr in custom_llm_instr_list if isinstance(instr, str)]
        )

    sql_gen_prompt_str_filled = SQL_GENERATION_BASE_PROMPT_TEMPLATE.format(
        default_top_clause=default_top_clause_str,
        default_limit=default_limit,
        max_limit=max_limit,
        custom_llm_instructions_str=custom_llm_instr_str_for_prompt,
        table_info="{table_info}", question="{question}", chat_history="{chat_history}"
    )
    sql_generation_prompt_obj = PromptTemplate(
        input_variables=["table_info", "question", "chat_history"],
        template=sql_gen_prompt_str_filled
    )
    
    generate_query_sub_chain = (
        RunnablePassthrough.assign(
            table_info=lambda x_original_input_dict: table_info_for_llm_prompt_str,
        )
        | sql_generation_prompt_obj | llm | StrOutputParser()
    )
    
    final_answer_prompt_obj = PromptTemplate.from_template(ANSWER_GENERATION_BASE_PROMPT_TEMPLATE)
    generate_final_answer_sub_chain = (final_answer_prompt_obj | llm | StrOutputParser())
    
    generated_sql_query_output: str = "NO_SQL_POSSIBLE_PRE_GENERATION"
    db_execution_result_output: str = "No se ejecutó consulta."
    final_llm_answer_output: str = "No se pudo determinar una respuesta final."

    try:
        print(f"SQLTOOLS_RUN_CHAIN: Generando SQL para (pregunta): '{question[:100]}...'")
        sql_gen_chain_input_dict = {"question": question, "chat_history": chat_history_str}
        
        generated_sql_query_raw_output = await generate_query_sub_chain.ainvoke(sql_gen_chain_input_dict)
        
        # ----->> MODIFICACIÓN: EXTRAER SQL DE BLOQUES MARKDOWN <<-----
        print(f"SQLTOOLS_RUN_CHAIN: Salida cruda del LLM (SQL Gen): '{generated_sql_query_raw_output}'")
        match = re.search(r"```(?:sql)?\s*(.*?)\s*```", generated_sql_query_raw_output, re.DOTALL | re.IGNORECASE)
        if match:
            generated_sql_query_output = match.group(1).strip()
            print(f"SQLTOOLS_RUN_CHAIN: SQL extraído de Markdown: '{generated_sql_query_output}'")
        else:
            generated_sql_query_output = generated_sql_query_raw_output.strip()
            # Si no hay markdown, es posible que el LLM haya respondido con "NO_SQL_POSSIBLE" directamente u otra cosa
            if "NO_SQL_POSSIBLE" not in generated_sql_query_output.upper() and not generated_sql_query_output.upper().startswith("SELECT"):
                 print(f"SQLTOOLS_RUN_CHAIN: ADVERTENCIA - Salida del LLM sin Markdown no parece SQL ni 'NO_SQL_POSSIBLE': '{generated_sql_query_output}'")
            else:
                 print(f"SQLTOOLS_RUN_CHAIN: SQL (o directiva) del LLM (sin Markdown detectado): '{generated_sql_query_output}'")
        # -----------------------------------------------------------
        
        is_valid_sql, validation_msg_or_none = _validate_generated_sql(generated_sql_query_output, sql_policy)
        
        if not is_valid_sql:
            print(f"SQLTOOLS_RUN_CHAIN: SQL inválido: {validation_msg_or_none}")
            db_execution_result_output = f"Consulta no ejecutada (inválida/no permitida): {validation_msg_or_none}"
            answer_gen_input_invalid_sql = {
                "question": question, "chat_history": chat_history_str, 
                "sql_query": generated_sql_query_output, 
                "sql_result": db_execution_result_output
            }
            final_llm_answer_output = await generate_final_answer_sub_chain.ainvoke(answer_gen_input_invalid_sql)
        elif generated_sql_query_output.strip().upper() == "NO_SQL_POSSIBLE":
            db_execution_result_output = "LLM determinó NO_SQL_POSSIBLE (no se intentó ejecutar)."
            answer_gen_input_no_sql = {
                "question": question, "chat_history": chat_history_str, 
                "sql_query": "NO_SQL_POSSIBLE", "sql_result": db_execution_result_output 
            }
            final_llm_answer_output = await generate_final_answer_sub_chain.ainvoke(answer_gen_input_no_sql)
        else:
            print(f"SQLTOOLS_RUN_CHAIN: Ejecutando SQL (limpio): '{generated_sql_query_output[:200]}...'")
            db_execution_result_output = await asyncio.to_thread( 
                execute_sql_query_with_db_instance, generated_sql_query_output, langchain_sql_db_for_execution
            )
            if "Error al ejecutar la consulta" in db_execution_result_output:
                print(f"SQLTOOLS_RUN_CHAIN: Error DURANTE ejecución SQL: {db_execution_result_output[:200]}")
            
            print("SQLTOOLS_RUN_CHAIN: Generando respuesta final basada en resultado de BD...")
            answer_gen_input_executed = {
                "question": question, "chat_history": chat_history_str, 
                "sql_query": generated_sql_query_output, "sql_result": db_execution_result_output
            }
            final_llm_answer_output = await generate_final_answer_sub_chain.ainvoke(answer_gen_input_executed)
    except Exception as e_lcel_run_exc:
        print(f"SQLTOOLS_RUN_CHAIN: Excepción INESPERADA en cadena Text-to-SQL: {type(e_lcel_run_exc).__name__} - {e_lcel_run_exc}")
        traceback.print_exc()
        generated_sql_query_output = generated_sql_query_output if generated_sql_query_output not in ["NO_SQL_POSSIBLE_PRE_GENERATION", ""] else "ERROR_UNHANDLED_EXCEPTION"
        db_execution_result_output = db_execution_result_output if db_execution_result_output not in ["No se ejecutó consulta.", ""] else f"Excepción: {e_lcel_run_exc}"
        try:
            error_answer_input = {
                "question": question, "chat_history": chat_history_str,
                "sql_query": generated_sql_query_output,
                "sql_result": f"Ocurrió un error interno al procesar la consulta: {e_lcel_run_exc}"
            }
            final_llm_answer_output = await generate_final_answer_sub_chain.ainvoke(error_answer_input)
        except Exception as e_final_answer_on_error:
            print(f"SQLTOOLS_RUN_CHAIN: Error al generar resp final LLM sobre excepción previa: {e_final_answer_on_error}")
            final_llm_answer_output = "Lo siento, ocurrió un error inesperado al procesar tu solicitud y no pude generar una respuesta detallada."

    print(f"SQLTOOLS_RUN_CHAIN: Respuesta Final a devolver (primeros 200 chars): {final_llm_answer_output[:200]}...")
    return {
        "generated_sql": generated_sql_query_output, 
        "db_query_result": str(db_execution_result_output),
        "final_answer_llm": final_llm_answer_output
    }