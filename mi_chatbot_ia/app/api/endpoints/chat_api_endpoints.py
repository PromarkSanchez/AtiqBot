# app/api/endpoints/chat_api_endpoints.py

# === Python y Librerías de Terceros ===
import time
import traceback
import asyncio
from typing import Dict, Any, List, Optional
import json
from operator import itemgetter
import re
from urllib.parse import quote_plus
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from redis.asyncio import Redis as AsyncRedis

# === LangChain Imports ===
from langchain_core.messages import HumanMessage, AIMessage, get_buffer_string
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate, MessagesPlaceholder # <-- ASEGURAR ESTA LÍNEA
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.documents import Document as LangchainCoreDocument
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_postgres.vectorstores import PGVector
 

# === Imports Locales (La Forma CORRECTA y Centralizada) ===
# Dependencias para inyección en el endpoint
from app.api.dependencies import get_crud_db, get_vector_store, get_app_state, get_redis_client
# Clases y configuración central
from app.core.app_state import AppState
from app.config import settings
# Herramientas de seguridad
from app.security.api_key_auth import get_validated_api_client
# Servicios (como el de caché)
from app.services import cache_service

# CRUD (Importamos las versiones ASÍNCRONAS donde sea necesario)
from app.crud import crud_virtual_agent_profile, crud_llm_model_config
from app.crud.crud_interaction_log import create_interaction_log_async

# Modelos y Schemas (Las "plantillas" de nuestros datos)
from app.models.api_client import ApiClient as ApiClientModel
from app.models.context_definition import ContextDefinition, ContextMainType
from app.models.virtual_agent_profile import VirtualAgentProfile
from app.schemas.schemas import ChatRequest, ChatResponse

# Lógica específica de la aplicación
from ._chat_history_logic import FullyCustomChatMessageHistory
from app.tools.sql_tools import run_db_query_chain

router = APIRouter(tags=["Chat"])

# --- Constantes y Clases de Excepción ---
CONV_STATE_AWAITING_NAME = "awaiting_name_confirmation"
CONV_STATE_AWAITING_TOOL_PARAMS = "awaiting_tool_parameters"

class AuthRequiredError(Exception):
    """Excepción especial para indicar que se requiere login."""
    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload
        super().__init__("Authentication is required for this action.")

async def _handle_human_handoff(uid: str, q: str) -> Dict[str, str]:
    """Genera un ticket de soporte de fallback."""
    ticket_id = f"TICKET-{int(time.time())}"
    return {"ticket_id": ticket_id, "response_text": f"He creado un ticket de soporte ({ticket_id})."}

# --- Funciones de Gestión de Estado ASÍNCRONAS ---

def _get_conversation_state_key(session_id: str) -> str:
    """Devuelve la clave estandarizada para el NOMBRE del estado de la conversación."""
    return f"conv:state:{session_id}"

def _get_tool_params_key(session_id: str) -> str:
    """Devuelve la clave estandarizada para los PARÁMETROS PARCIALES de la herramienta."""
    return f"conv:params:{session_id}"

def _get_user_name_key(session_id: str) -> str:
    """Devuelve la clave para el nombre de usuario de la sesión."""
    return f"conv:username:{session_id}"

async def get_conversation_state_async(redis_client: Optional[AsyncRedis], session_id: str) -> Dict[str, Any]:
    """Recupera el estado completo de la conversación de forma asíncrona."""
    if not redis_client:
        return {"state_name": None, "partial_parameters": {}}
        
    state_key = _get_conversation_state_key(session_id)
    params_key = _get_tool_params_key(session_id)
    username_key = _get_user_name_key(session_id)

    state, params, username  = await asyncio.gather(
        cache_service.get_generic_cache_async(redis_client, state_key),
        cache_service.get_generic_cache_async(redis_client, params_key),
        cache_service.get_generic_cache_async(redis_client, username_key)
    )
    
    return {
        "state_name": state if isinstance(state, str) else None,
        "partial_parameters": params if isinstance(params, dict) else {},
        "user_name": username if isinstance(username, str) else None
    }

async def save_conversation_state_async(
    redis_client: Optional[AsyncRedis], 
    session_id: str, 
    state_name: Optional[str], 
    partial_params: Optional[Dict[str, Any]], 
    ttl_seconds: int = 300
):
    """Guarda el estado. Ahora también maneja el 'user_name' si viene en partial_params."""
    if not redis_client: return
        
    state_key = _get_conversation_state_key(session_id)
    params_key = _get_tool_params_key(session_id)
    username_key = _get_user_name_key(session_id)

    # Preparamos los parámetros de herramienta sin el nombre de usuario
    tool_params_to_save = partial_params.copy() if partial_params else {}
    user_name_to_save = tool_params_to_save.pop("user_name", None)

    tasks = []
    
    # Manejar estado y parámetros de herramienta
    if state_name is None:
        tasks.extend([
            cache_service.delete_generic_cache_async(redis_client, state_key),
            cache_service.delete_generic_cache_async(redis_client, params_key)
        ])
    else:
        tasks.append(cache_service.set_generic_cache_async(redis_client, state_key, state_name, ttl_seconds=ttl_seconds))
        if tool_params_to_save: # Solo guardamos si hay algo que guardar
            tasks.append(cache_service.set_generic_cache_async(redis_client, params_key, tool_params_to_save, ttl_seconds=ttl_seconds))
        else:
            tasks.append(cache_service.delete_generic_cache_async(redis_client, params_key))

    # Manejar nombre de usuario por separado (con un TTL más largo quizás)
    if user_name_to_save:
        tasks.append(cache_service.set_generic_cache_async(redis_client, username_key, user_name_to_save, ttl_seconds=180)) # Guardamos el nombre por 1 hora

    if tasks:
        await asyncio.gather(*tasks)

# --- GRUPO 4: AGENTES Y HANDLERS DE LÓGICA ---

async def master_router_agent(
    question: str,
    has_db_capability: bool,
    has_doc_capability: bool,
    llm: BaseChatModel

) -> str:
    """
    Decide qué herramienta usar: RAG, BD o Despedida.
    """
    if not has_db_capability and not has_doc_capability: return "NO_CAPABILITY"

    # Si solo tiene una capacidad, la decisión es directa, a menos que sea una despedida.
    is_farewell_simple_check = any(word in question.lower() for word in ["gracias", "adiós", "chao", "hasta luego", "eso es todo"])
    if is_farewell_simple_check:
        return "FAREWELL_HANDLER"

    if has_db_capability and not has_doc_capability: return "DATABASE_TOOL"
    if has_doc_capability and not has_db_capability: return "DOCUMENT_RETRIEVER"


   
    prompt = ChatPromptTemplate.from_messages([
         
        (f"system",
         "Tu  Eres un agente enrutador experto. Tu única tarea es seleccionar la herramienta más adecuada para responder la pregunta del usuario. "
         "Responde únicamente con el nombre de la herramienta elegida en formato JSON.\n\n"
         "Herramientas Disponibles:\n"
         "1. `DOCUMENT_RETRIEVER`: Úsala para preguntas generales, conceptuales o teóricas sobre los temas u titulos del documento. Ejemplos: '¿como accedo a mi intranet?', 'explícame sobre blackboard', 'quiero saber sobre mis horarios', 'me puedes dar un resumen de lo que sabes'.\n"
         "2. `DATABASE_TOOL`: Úsala para preguntas que piden datos específicos y personales del usuario. Ejemplos: 'quiero saber mis notas', '¿cuál es mi promedio?', 'dame mi horario'.\n"
         "3. `FAREWELL_HANDLER`: Úsala si el usuario se está despidiendo o agradeciendo para finalizar la conversación. Ejemplos: 'gracias', 'eso es todo por ahora', 'adiós'.\n"),
        ("human", "Pregunta del usuario: {question}\n\nRespuesta JSON (solo la clave 'tool_to_use'):"),
    ])
    
    chain = prompt | llm | JsonOutputParser()
    
    try:
        response = await chain.ainvoke({"question": question})
        selected_tool = response.get("tool_to_use")
        if selected_tool in ["DOCUMENT_RETRIEVER", "DATABASE_TOOL", "FAREWELL_HANDLER"]:
            print(f"MASTER_ROUTER: Herramienta seleccionada: {selected_tool}")
            return selected_tool
    except Exception as e:
        print(f"MASTER_ROUTER: Error al seleccionar herramienta: {e}. Usando fallback.")

    return "DOCUMENT_RETRIEVER"

async def handle_greeting(vap: VirtualAgentProfile, llm: BaseChatModel, req: ChatRequest) -> Dict[str, Any]:
    """Maneja el saludo inicial. Tu lógica original se mantiene."""
    log = {"intent": "GREETING"}
    chain = ChatPromptTemplate.from_template(vap.greeting_prompt) | llm | StrOutputParser()
    # Cambiamos "Usuario" por "" para no inyectar un nombre falso.
    final_bot_response = await chain.ainvoke({"user_name": req.user_name or ""})
    
    next_state, next_params = None, None
    if vap.name_confirmation_prompt:
        next_state = CONV_STATE_AWAITING_NAME
        next_params = {}
        
    return {"response": final_bot_response, "metadata": {}, "log": log, "next_state": next_state, "next_params": next_params}

async def handle_name_and_query_extraction(
    req: ChatRequest,
    vap: VirtualAgentProfile,
    llm: BaseChatModel,
    user_dni: Optional[str],
    history_list: List,
    active_contexts: List[ContextDefinition],
    all_allowed_contexts: List[ContextDefinition],
    db: AsyncSession,
    vector_store: PGVector,
    app_state: AppState,
    redis_client: Optional[AsyncRedis]
) -> Dict[str, Any]:
    """
    Handler robusto que extrae, valida, y decide el flujo conversacional correcto,
    incluyendo el manejo proactivo de saludos simples.
    """
    log = {"intent": "COMBINED_NAME_AND_QUERY_EVALUATION", "agent_used": vap.name}

    # (Aquí va el nuevo `extraction_prompt_template_str` que te puse arriba)
    agent_name = vap.name or "Hered-IA"
    extraction_prompt_template_str = (
        f"Tú eres {agent_name}. Tu única tarea es analizar el mensaje de un usuario y extraer dos datos: "
        "1. `extracted_name`: El nombre de pila del usuario, si lo proporciona. "
        "2. `follow_up_query`: Una pregunta de seguimiento, si la hace. "
        "Responde ÚNICAMENTE con un objeto JSON. Si un dato no está presente, usa el valor JSON `null` (no el string \"null\"). "
        "**Regla Crítica: NO INVENTES una `follow_up_query` si el usuario solo dio un saludo simple.**\n\n"
        "EJEMPLOS CLAVE DE TU ANÁLISIS:\n"
        "Input del usuario: 'Hola'\n"
        "Tu JSON de análisis: {{\"extracted_name\": null, \"follow_up_query\": null}}\n\n"
        "Input del usuario: 'Buenos días'\n"
        "Tu JSON de análisis: {{\"extracted_name\": null, \"follow_up_query\": null}}\n\n"
        "Input del usuario: 'Me llamo Juaneco'\n"
        "Tu JSON de análisis: {{\"extracted_name\": \"Juaneco\", \"follow_up_query\": null}}\n\n"
        "Input del usuario: 'Soy Ana y quería saber sobre mi intranet'\n"
        "Tu JSON de análisis: {{\"extracted_name\": \"Ana\", \"follow_up_query\": \"quería saber sobre mi intranet\"}}\n\n"
        "Input del usuario: '¿cuál es mi horario?'\n"
        "Tu JSON de análisis: {{\"extracted_name\": null, \"follow_up_query\": \"¿cuál es mi horario?\"}}\n\n"
        "--- INICIO DEL MENSAJE DEL USUARIO PARA ANALIZAR ---\n"
        "Mensaje: \"{user_input}\"\n"
        "Tu JSON de análisis:"
    )

    extraction_prompt_template = ChatPromptTemplate.from_template(extraction_prompt_template_str)
    extraction_chain = extraction_prompt_template | llm | JsonOutputParser()

    try:
        extraction_result = await extraction_chain.ainvoke({"user_input": req.message.strip()})
        extracted_name_raw = extraction_result.get("extracted_name")
        follow_up_query = extraction_result.get("follow_up_query")
    except Exception as e:
        print(f"WARN: La extracción combinada falló: {e}. Fallback a saludo proactivo.")
        extracted_name_raw = None
        follow_up_query = None # Forzamos el caso de saludo

    # --- Validación de Nombre (la mantenemos porque es crucial) ---
    final_name_to_save = None
    INVALID_NAME_VALUES = {'', 'null', 'none', 'n/a', 'usuario', ':null'}
    if extracted_name_raw:
        candidate_name = str(extracted_name_raw).strip()
        if candidate_name and candidate_name.lower() not in INVALID_NAME_VALUES:
            final_name_to_save = candidate_name.capitalize()
            log["extracted_user_name"] = final_name_to_save
            req.user_name = final_name_to_save

    # --- NUEVA LÓGICA DE DECISIÓN (Más clara y robusta) ---

    # CASO A: El usuario hizo una pregunta (con o sin nombre). ¡Máxima prioridad!
    if follow_up_query:
        log["intent"] = "QUERY_DETECTED"
        new_req = req.copy(update={"message": follow_up_query})
        
        result = await handle_new_question(
            req=new_req, user_dni=user_dni, llm=llm, history_list=[],
            active_contexts=active_contexts, all_allowed_contexts=all_allowed_contexts, vap=vap, 
            db=db, vector_store=vector_store, app_state=app_state, redis_client=redis_client
        )

        next_params = result.get("next_params") or {}
        if final_name_to_save:
            next_params["user_name"] = final_name_to_save
        result["next_params"] = next_params
        result["next_state"] = None if result.get("next_state") != CONV_STATE_AWAITING_TOOL_PARAMS else result["next_state"]
        return result
    
    # CASO B: El usuario SÓLO dio un nombre válido.
    elif final_name_to_save:
        log["intent"] = "NAME_CONFIRMATION_ONLY"
        response_template = "¡Entendido, {user_name}! Ahora sí, ¿en qué puedo ayudarte?"
        final_bot_response = response_template.format(user_name=final_name_to_save)
        
        return {
            "response": final_bot_response,
            "metadata": {}, "log": log, "next_state": None,
            "next_params": {"user_name": final_name_to_save}
        }
        
    # CASO C: El usuario dio un saludo simple ("Hola") o algo que no se entendió. ¡NUESTRO NUEVO MANEJO!
    else:
        log["intent"] = "SIMPLE_GREETING_OR_UNRECOGNIZED"
        print("HANDLER_LOGIC: Saludo simple detectado. Respondiendo proactivamente.")

        # Generamos una respuesta que guía al usuario
        final_bot_response = (
            "¡Claro! Con gusto te ayudo. "
            "Puedo darte información sobre tus horarios, notas, o resolver dudas generales de la intranet. "
            "¿Qué te gustaría consultar?"
        )
        
        return {
            "response": final_bot_response,
            "metadata": {}, "log": log, "next_state": None,
            "next_params": {} # MUY IMPORTANTE: no guardamos ningún nombre.
        }

async def handle_name_confirmation(question: str, vap: VirtualAgentProfile, llm: BaseChatModel) -> Dict[str, Any]:
    """
    Maneja la confirmación, extrae el nombre y lo devuelve para ser guardado.
    """
    log = {"intent": "NAME_CONFIRMATION"}
    
    extraction_prompt_template = (
        "Eres un sistema de extracción de entidades. Analiza el siguiente texto proporcionado por un usuario "
        "y extrae su nombre de pila. Responde ÚNICAMENTE con un objeto JSON con la clave 'extracted_name'. Si no encuentras un nombre, devuelve null.\n\n"
        "Texto del usuario: \"{user_provided_name}\"\n"
        "JSON:"
    )
    extraction_chain = (
        ChatPromptTemplate.from_template(extraction_prompt_template) 
        | llm 
        | JsonOutputParser()
    )
    
    extracted_name = "" # <-- Empezamos con un valor seguro
    try:
        extraction_result = await extraction_chain.ainvoke({"user_provided_name": question.strip()})
        # Usamos .get() que devuelve None por defecto si no encuentra la clave
        name_from_llm = extraction_result.get("extracted_name")
        if name_from_llm: # Solo procesamos si el LLM devolvió algo
             extracted_name = str(name_from_llm).strip().capitalize()
    except Exception:
        # Fallback si el JSON falla, pero SIN usar "Usuario"
        print(f"WARN: Fallo en extracción de nombre en handle_name_confirmation. Fallback a cadena vacía.")
        extracted_name = ""

    # Ahora la respuesta se adapta
    if extracted_name:
        response_template = "¡Entendido, {user_name}! Ahora sí, ¿en qué puedo ayudarte?"
        final_bot_response = response_template.format(user_name=extracted_name)
    else:
        # Si no se extrajo nombre, usamos una respuesta genérica
        final_bot_response = "¡Entendido! Ahora sí, ¿en qué puedo ayudarte?"

    return {
        "response": final_bot_response,
        "metadata": {},
        "log": log,
        "next_state": None, 
        # Si extracted_name está vacío, se guardará una cadena vacía. ¡Perfecto!
        "next_params": {"user_name": extracted_name}
    }

async def is_name_or_query_classifier_chain(question: str, llm: BaseChatModel) -> bool:
    """
    Clasifica si la entrada de un usuario es un nombre o una consulta directa.
    
    Devuelve:
        - True si la entrada parece ser un nombre o una presentación.
        - False si la entrada es una pregunta o una consulta.
    """
    classifier_prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Eres un clasificador de intenciones llamado Hered-IA experto y muy rápido. El asistente virtual acaba de preguntar al usuario su nombre. "
         "Analiza la siguiente respuesta del usuario y determina si es una presentación (un nombre) o si es una consulta/pregunta sobre un tema completamente diferente. "
         "Responde únicamente con un objeto JSON con una única clave booleana 'is_name'. "
         "Ejemplos de nombre (is_name: true): 'Soy Juan', 'Me llamo Ana', 'puedes llamarme Pedro', 'Mi nombre es María'. "
         "Ejemplos de consulta (is_name: false): '¿cuáles son mis notas?', 'quiero saber de mi blackboard', 'necesito ayuda con mi horario', 'olvídalo, quiero saber otra cosa'."
        ),
        ("human", "Respuesta del usuario: \"{user_input}\"\n\nJSON:")
    ])
    
    chain = classifier_prompt | llm | JsonOutputParser()
    
    try:
        response = await chain.ainvoke({"user_input": question})
        # Devuelve el valor booleano, con un fallback seguro a 'False' si hay algún problema
        return response.get("is_name", False) 
    except Exception as e:
        print(f"WARN: Clasificador de nombre/consulta falló: {e}. Asumiendo que es una consulta.")
        return False # Si el LLM falla, es más seguro tratarlo como una consulta para no atascar al bot.


# En app/api/endpoints/chat_api_endpoints.py

async def handle_farewell(vap: VirtualAgentProfile, req: ChatRequest, llm: BaseChatModel) -> Dict[str, Any]:
    """Maneja la despedida de forma controlada y robusta, construyendo el prompt en Python."""
    log = {"intent": "FAREWELL"}

    # --- LÓGICA CLAVE: PREPARAMOS LA VARIABLE DEL NOMBRE EN PYTHON ---
    # Usamos nuestra lista negra para asegurar que no pasen valores no deseados.
    INVALID_NAME_VALUES = {'', 'null', 'none', 'n/a', 'usuario', ':null'}
    user_name_for_prompt = ""
    if req.user_name and str(req.user_name).strip().lower() not in INVALID_NAME_VALUES:
        user_name_for_prompt = req.user_name.strip()

    # --- CONSTRUCCIÓN DINÁMICA DE LA INSTRUCCIÓN DE PERSONALIZACIÓN ---
    # Aquí está la magia: decidimos en Python qué instrucción simple le daremos al LLM.
    if user_name_for_prompt:
        # CASO 1: Tenemos un nombre real. La instrucción es directa.
        personalization_instruction = (
            f"El nombre del usuario es **{user_name_for_prompt}**. "
            f"Personaliza la despedida dirigiéndote a él por su nombre (ej. '¡Hasta luego, {user_name_for_prompt}!')."
        )
        print(f"FAREWELL_LOGIC: Se usará el nombre '{user_name_for_prompt}' para la despedida.")
    else:
        # CASO 2: NO tenemos nombre. La instrucción también es directa.
        personalization_instruction = (
            "No se ha proporcionado el nombre del usuario. "
            "Genera una despedida amable y general sin usar ningún nombre."
        )
        print("FAREWELL_LOGIC: No se usará nombre para la despedida (genérica).")
        
    # --- PROMPT FINAL SIMPLIFICADO ---
    # El prompt ahora es muy tonto. Solo inserta la instrucción que ya preparamos.
    farewell_prompt_template = (
        "Tu única tarea es generar una despedida corta y amable para un usuario. "
        "{instruction}. " # <-- Aquí va nuestra instrucción ya procesada.
        "Agradécele siempre por la conversación y anímale a volver si tiene más dudas. "
        "Termina con un emoji amigable."
    )
    
    chain = ChatPromptTemplate.from_template(farewell_prompt_template) | llm | StrOutputParser()

    # Invocamos la cadena con la instrucción específica que creamos.
    final_bot_response = await chain.ainvoke({"instruction": personalization_instruction})
        
    return {"response": final_bot_response, "metadata": {}, "log": log, "next_state": None, "next_params": None}

async def handle_tool_clarification(
    req: ChatRequest, 
    conversation_state: Dict, 
    llm: BaseChatModel, 
    history_list: List, 
    active_contexts: List[ContextDefinition]
) -> Dict[str, Any]:
    """
    Maneja un turno de una conversación de clarificación ya iniciada.
    """
    # Recupera el contexto de la base de datos que estamos usando, guardado en el estado
    ctx_id_from_state = conversation_state["partial_parameters"].get("context_id")
    target_context = next((c for c in active_contexts if c.id == ctx_id_from_state), None)
    if not target_context:
        raise ValueError(f"Error crítico: No se pudo recargar el contexto {ctx_id_from_state} desde el estado.")
    
    # Llama a la cadena SQL y le pasa los parámetros parciales que teníamos guardados en Redis
    tool_call_result = await run_db_query_chain(
        question=req.message,
        chat_history_str=get_buffer_string(history_list),
        db_conn_config=target_context.db_connection_config,
        processing_config=target_context.processing_config or {},
        llm=llm,
        user_dni=req.user_dni, 
        user_name=req.user_name,
        partial_params_from_redis=conversation_state.get("partial_parameters")
    )
    
    final_bot_response = tool_call_result.get("final_answer")
    metadata = tool_call_result.get("metadata", {})
    log = {"intent": tool_call_result.get("intent")}

    # Si la herramienta AÚN necesita más información, mantenemos el estado
    # y actualizamos los parámetros parciales con la nueva información que encontramos.
    next_state, next_params = None, None
    if tool_call_result.get("intent") == "CLARIFICATION_REQUIRED":
        next_state = CONV_STATE_AWAITING_TOOL_PARAMS
        next_params = tool_call_result["metadata"].get("partial_parameters", {})
        next_params["context_id"] = target_context.id # Mantenemos el ID del contexto
    
    return {"response": final_bot_response, "metadata": metadata, "log": log, "next_state": next_state, "next_params": next_params}
# En app/api/endpoints/chat_api_endpoints.py

# En app/api/endpoints/chat_api_endpoints.py

# UBICACIÓN: app/api/endpoints/chat_api_endpoints.py

async def handle_new_question(
    req: ChatRequest, 
    user_dni: Optional[str],
    llm: BaseChatModel, 
    history_list: List,
    active_contexts: List[ContextDefinition], 
    all_allowed_contexts: List[ContextDefinition],
    vap: VirtualAgentProfile, 
    db: AsyncSession,
    vector_store: PGVector,
    app_state: AppState,
    redis_client: Optional[AsyncRedis]
) -> Dict[str, Any]:
    """
    Maneja una nueva pregunta con una capa de seguridad explícita y flujo de datos corregido.
    """
    # --- 1. Determinar contextos y capacidades ---
    active_db_ctx = next((c for c in active_contexts if c.main_type == ContextMainType.DATABASE_QUERY), None)
    active_doc_ctx = next((c for c in active_contexts if c.main_type == ContextMainType.DOCUMENTAL), None)
    
    has_db_capability = any(c.main_type == ContextMainType.DATABASE_QUERY for c in all_allowed_contexts)
    has_doc_capability = any(c.main_type == ContextMainType.DOCUMENTAL for c in all_allowed_contexts)
    
    # --- 2. Enrutar Intención ---
    selected_tool = await master_router_agent(req.message, has_db_capability, has_doc_capability, llm)
    
    # <<<<<<<<<<<<<<<<< LA NUEVA LÓGICA COMIENZA AQUÍ >>>>>>>>>>>>>>>>>

    # --- CONSTRUCCIÓN DINÁMICA DEL SYSTEM PROMPT ---
    base_system_prompt = vap.system_prompt
    final_system_prompt = base_system_prompt

    # Si conocemos el nombre del usuario (de Redis o extraído en este turno), enriquecemos el prompt.
    # El `req.user_name` fue actualizado por nuestro handler `handle_name_and_query_extraction`.
    
    if req.user_name and req.user_name.strip().lower() != 'usuario':
        # Si la condición se cumple, es un nombre real. Construimos la instrucción.
        personalization_instruction = (
            f"\n\n--- DIRECTIVA DE PERSONALIZACIÓN Y VERACIDAD (REGLA MAESTRA) ---\n"
            f"El nombre del usuario es **{req.user_name.strip()}**. Debes dirigirte a él/ella por su nombre para ser amigable.\n"
            f"**PERO LA REGLA MÁS IMPORTANTE ES:** Tu respuesta a {req.user_name.strip()} debe provenir **ÚNICA, EXCLUSIVA Y ESTRICTAMENTE** del CONTEXTO que se te proporciona más abajo. "
            f"NO USES tu conocimiento general. Si el CONTEXTO no contiene la respuesta exacta (ej. URLs, nombres de servicios, números de teléfono), di que no tienes esa información específica en tus documentos, pero puedes ayudar con lo que sí sabes. NO INVENTES NADA, ni siquiera URLs o nombres de departamentos."
        )
        final_system_prompt += personalization_instruction
        print(f"PROMPT_LOGIC: System prompt enriquecido con el nombre '{req.user_name.strip()}' y regla anti-alucinación.")
    else:
        # (Opcional) Esto es útil para saber qué pasó en tus logs.
        # Si no hay nombre o es "Usuario", simplemente no hacemos nada y el prompt no se modifica.
        print(f"PROMPT_LOGIC: No se proporcionó un nombre específico o era el valor por defecto. Se omite la personalización.")

    # <<<<<<<<<<<<<<<<< LA NUEVA LÓGICA TERMINA AQUÍ >>>>>>>>>>>>>>>>>

    # --- 3. Control de Acceso y Ejecución ---
    
    # --- CASO NUEVO: Despedida ---
    if selected_tool == "FAREWELL_HANDLER":
        print("SECURITY_GATE: Intención de despedida detectada. Llamando a handle_farewell.")
        # <<< LA CORRECCIÓN ES AÑADIR `req=req` A LA LLAMADA
        return await handle_farewell(vap=vap, req=req, llm=llm)


    # --- CASO A: Intención es usar Base de Datos ---
    elif  selected_tool == "DATABASE_TOOL":
        
        # Primero, la muralla de seguridad
        if not active_db_ctx:
            print("SECURITY_GATE: Denegado. Se requiere autenticación para DATABASE_TOOL.")
            raise AuthRequiredError({
                "intent": "AUTH_REQUIRED", 
                "bot_response": "Para esta consulta, necesito que inicies sesión.", 
                "metadata_details_json": {"action_required": "request_login"}
            })
        
        # Si el acceso está permitido, ejecutar la herramienta para un TURNO NUEVO.
        print("SECURITY_GATE: Permitido. Ejecutando DATABASE_TOOL (primer turno).")
        tool_call_result = await run_db_query_chain(
            question=req.message, 
            chat_history_str=get_buffer_string(history_list),
            db_conn_config=active_db_ctx.db_connection_config, 
            processing_config=active_db_ctx.processing_config or {},
            llm=llm, 
            user_dni=req.user_dni,
            user_name=req.user_name,
            partial_params_from_redis=None  # <-- Clave: Es una pregunta nueva, no hay estado previo.
        )
        
        final_bot_response = tool_call_result.get("final_answer")
        metadata = tool_call_result.get("metadata", {})
        log = {"intent": tool_call_result.get("intent")}
        
        # Si la herramienta necesita más datos, establecemos el estado para el siguiente turno.
        next_state, next_params = None, None
        if tool_call_result.get("intent") == "CLARIFICATION_REQUIRED":
            next_state = CONV_STATE_AWAITING_TOOL_PARAMS
            next_params = metadata.get("partial_parameters", {})
            next_params["context_id"] = active_db_ctx.id
        
        return {"response": final_bot_response, "metadata": metadata, "log": log, "next_state": next_state, "next_params": next_params}

    # --- CASO B: Intención es usar Documentos (RAG) ---
    elif selected_tool == "DOCUMENT_RETRIEVER":
        
        # Muralla de seguridad para documentos
        if not active_doc_ctx:
            print("SECURITY_GATE: Denegado. No hay un contexto de Documentos activo.")
            return {"response": "Lo siento, no tengo acceso a los documentos necesarios en este momento.", "metadata": {}, "log": {"intent": "NO_CONTEXT_AVAILABLE"}, "next_state": None, "next_params": None}

        # Ejecución de la cadena RAG con el historial gestionado de forma nativa
        print("SECURITY_GATE: Permitido. Ejecutando DOCUMENT_RETRIEVER (RAG).")
        
        # Esta limpieza de mensajes específicos es una buena práctica, la conservamos
        clean_history_list = [msg for msg in history_list if not (isinstance(msg, AIMessage) and ("nota final del curso es" in msg.content or "son las siguientes:" in msg.content))]

        # Prompt para volver la pregunta actual una pregunta independiente usando el historial
        condense_q_prompt = PromptTemplate.from_template(settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE)

        #  ¡EL CAMBIO MÁS IMPORTANTE! 
        # El prompt final se ensambla dinámicamente, tratando cada parte como un bloque.
        # Esto evita la contaminación del historial y permite que el LLM lo entienda nativamente.
        answer_prompt = ChatPromptTemplate.from_messages([
            ("system", vap.system_prompt), # Tu prompt principal de la BD (ya modificado).
            MessagesPlaceholder(variable_name="chat_history"), # Aquí LangChain insertará la lista de mensajes.
            ("human", "{question}") # La pregunta final independiente del usuario.
        ])
        
        retriever = vector_store.as_retriever(search_kwargs={"k": 3, "filter": {"context_name": active_doc_ctx.name}})

        def format_docs(docs: List[LangchainCoreDocument]):
            return "\n\n".join(d.page_content for d in docs)

        # 1. Cadena para crear la pregunta independiente (mantiene la conversación fluida)
        standalone_question_chain = RunnablePassthrough.assign(
            chat_history=lambda x: get_buffer_string(clean_history_list)
        ) | condense_q_prompt | llm | StrOutputParser()
        
        # 2. Cadena para recuperar documentos usando la pregunta independiente
        retrieved_documents_chain = RunnablePassthrough.assign(
            standalone_question=standalone_question_chain
        ).assign(context_docs=itemgetter("standalone_question") | retriever)
        
        # 3. Cadena final que une todo
        # Nota cómo pasamos 'chat_history' como una lista y 'question' como el string independiente.
        final_rag_chain = (
            retrieved_documents_chain |
            RunnablePassthrough.assign(
                # Pasamos el historial como una LISTA de mensajes, no como un texto plano.
                chat_history=lambda x: clean_history_list, 
                question=itemgetter("standalone_question"),
                context=itemgetter("context_docs") | RunnableLambda(format_docs),
            ) |
            answer_prompt | llm | StrOutputParser()
        )

        chain_input = {"question": req.message}
        final_bot_response = await final_rag_chain.ainvoke(chain_input)
        
        retrieved_data = await retrieved_documents_chain.ainvoke(chain_input)
        source_documents = retrieved_data.get("context_docs", [])
        
        metadata = {"source_documents": [{"source": doc.metadata.get("source", "N/A"), "page": doc.metadata.get("page_number", "N/A")} for doc in source_documents]} # Ajusta "page_number" si usas otro nombre
        log = {"intent": "RAG_DOCUMENTAL"}
        
        return {"response": final_bot_response, "metadata": metadata, "log": log, "next_state": None, "next_params": None}  
    
    # --- CASO C: Fallback ---
    else:
        return {"response": "Lo siento, no estoy seguro de cómo ayudarte con eso. ¿Puedes intentarlo de otra manera?", "metadata": {}, "log": {"intent": "NO_CAPABILITY"}, "next_state": None, "next_params": None}# Función route_request VERIFICADA

# UBICACIÓN: app/api/endpoints/chat_api_endpoints.py
# VERSIÓN FINAL, COMPLETA Y VERIFICADA DE route_request.

async def route_request(
    req: ChatRequest, user_dni: Optional[str], conversation_state: Dict, llm: BaseChatModel, history_list: List,
    active_contexts: List[ContextDefinition], all_allowed_contexts: List[ContextDefinition],
    vap: VirtualAgentProfile, db: AsyncSession, 
    redis_client: Optional[AsyncRedis], vector_store: PGVector, app_state: AppState
) -> Dict[str, Any]:
    """
    Orquesta la llamada al handler correcto. Diseño verificado para mantener la
    estabilidad de la lógica existente mientras se añade la nueva funcionalidad.
    """
    current_state = conversation_state.get("state_name")
    
    # --- REGLA 1: Saludo inicial. [LÓGICA INTACTA] ---
    # Maneja exclusivamente el primer mensaje si es la señal de inicio.
    if not history_list and req.message == "__INICIAR_CHAT__":
        print("ROUTE_LOGIC: Turno 1. Llamando a handle_greeting.")
        return await handle_greeting(vap, llm, req)
    
    # --- REGLA 2: Potencial turno de nombre/consulta combinada. [NUEVA LÓGICA DELEGADA] ---
    # Detecta si estamos en el turno de pedir el nombre.
    is_potentially_name_turn = (current_state == CONV_STATE_AWAITING_NAME) or \
                               (len(history_list) == 1 and redis_client is None and vap.name_confirmation_prompt)
    
    if is_potentially_name_turn:
        # En lugar de lógica compleja aquí, se delega a un handler especializado.
        print("ROUTE_LOGIC: Estado AWAITING_NAME detectado. Delegando a handle_name_and_query_extraction.")
        return await handle_name_and_query_extraction(
            # Se le pasan todas las herramientas necesarias para que pueda operar de forma autónoma.
            req=req, vap=vap, llm=llm, user_dni=user_dni, history_list=history_list,
            active_contexts=active_contexts, all_allowed_contexts=all_allowed_contexts, db=db,
            vector_store=vector_store, app_state=app_state, redis_client=redis_client
        )

    # --- REGLA 3: Clarificación de herramientas. [LÓGICA INTACTA] ---
    # Si estamos a mitad de una conversación multi-turno con una herramienta, se continúa ese flujo.
    if current_state == CONV_STATE_AWAITING_TOOL_PARAMS:
        print("ROUTE_LOGIC: Estado 'AWAITING_TOOL_PARAMS' detectado. Llamando a handle_tool_clarification.")
        return await handle_tool_clarification(req, conversation_state, llm, history_list, active_contexts)
    
    # --- REGLA 4: Pregunta nueva por defecto. [LÓGICA INTACTA] ---
    # Si ninguna de las condiciones anteriores se cumple, es una pregunta estándar.
    print("ROUTE_LOGIC: No hay estado de conversación activo. Enrutando como nueva pregunta.")
    return await handle_new_question(
        req=req, user_dni=user_dni, llm=llm, history_list=history_list, active_contexts=active_contexts,
        all_allowed_contexts=all_allowed_contexts, vap=vap, db=db, vector_store=vector_store,
        app_state=app_state, redis_client=redis_client
    )
# ==========================================================
# ======>   EL ENDPOINT FINAL (UNIFICADO Y ROBUSTO)      <======
# ==========================================================

@router.post("/api/v1/chat/", response_model=ChatResponse)
async def process_chat_message(
    req: ChatRequest,
    # --- Inyección de Dependencias Completa ---
    client: ApiClientModel = Depends(get_validated_api_client),
    db: AsyncSession = Depends(get_crud_db),
    app_state: AppState = Depends(get_app_state),
    redis_client: Optional[AsyncRedis] = Depends(get_redis_client),
    vector_store: PGVector = Depends(get_vector_store)
):
    start_time, question, s_id = time.time(), req.message, req.session_id
    log: Dict[str, Any] = {"user_dni": req.user_dni or s_id, "api_client_name": client.name, "user_message": question}
    history = FullyCustomChatMessageHistory(s_id, redis_client=redis_client)
    final_bot_response, metadata_response = "Lo siento, ha ocurrido un error.", {}

    try:
        # --- 1. CARGA DE DEPENDENCIAS ---
        api_client_settings = client.settings or {}
        allowed_ctx_ids = api_client_settings.get("allowed_context_ids", [])
        if not allowed_ctx_ids: raise HTTPException(403, "API Key sin contextos.")

        stmt_base = select(ContextDefinition).where(ContextDefinition.id.in_(allowed_ctx_ids), ContextDefinition.is_active == True)
        all_allowed_contexts_stmt = stmt_base.options(selectinload(ContextDefinition.db_connection_config))
        all_allowed_contexts = (await db.execute(all_allowed_contexts_stmt)).scalars().unique().all()

        if req.is_authenticated_user:
            active_contexts = all_allowed_contexts
        else:
            active_contexts = [c for c in all_allowed_contexts if c.is_public]

        if not active_contexts: raise HTTPException(404, "No hay contextos válidos para esta solicitud.")

        

        
            
        vap_id = api_client_settings.get("default_virtual_agent_profile_id_override") or active_contexts[0].virtual_agent_profile_id
        vap = await crud_virtual_agent_profile.get_fully_loaded_profile(db, vap_id)
        llm_cfg_id = (api_client_settings.get("default_llm_model_config_id_override") or vap.llm_model_config_id or active_contexts[0].default_llm_model_config_id)
        llm_config = await crud_llm_model_config.get_llm_model_config_by_id(db, llm_cfg_id)
        if not llm_config: raise HTTPException(404, "Configuración LLM no encontrada.")
        
        # === ¡AQUÍ ESTÁ LA NUEVA LÓGICA DE DECISIÓN! ===
        final_temperature = 0.3 # Valor de fallback por si todo falla

        # 1. Empezamos con la temperatura por defecto del MODELO
        if llm_config.default_temperature is not None:
            final_temperature = llm_config.default_temperature
            print(f"TEMPERATURE_LOGIC: Usando temp. del modelo: {final_temperature}")

        # 2. Si el AGENTE tiene un override, ESTE GANA.
        #    (Asegúrate de que tu tabla `virtual_agent_profiles` tenga la columna `temperature_override`)
        if hasattr(vap, 'temperature_override') and vap.temperature_override is not None:
            final_temperature = vap.temperature_override
            print(f"TEMPERATURE_LOGIC: ¡OVERRIDE! Usando temp. del agente: {final_temperature}")

        # 3. Llamamos a get_cached_llm con la temperatura final decidida.
        llm = await app_state.get_cached_llm(
            model_config=llm_config,
            temperature_to_use=final_temperature
        )
        # Corrección 1: Llamada al método de caché de LLM en AppState        
        # Corrección 4: Llamada al método async de historial
        history_list = await history.get_messages_async()
        log["llm_model_used"] = llm_config.display_name

        # --- 2. RECUPERAR ESTADO Y DELEGAR AL ENRUTADOR ---
        conversation_state = await get_conversation_state_async(redis_client, s_id)
        
        if conversation_state.get("user_name"):
            req.user_name = conversation_state["user_name"]
            print(f"SESSION_LOGIC: Nombre '{req.user_name}' recuperado de Redis para la sesión {s_id}.")

        handler_result = await route_request(
            req=req,
            user_dni=req.user_dni, 
            conversation_state=conversation_state, 
            llm=llm, 
            history_list=history_list,
            active_contexts=active_contexts, 
            all_allowed_contexts=all_allowed_contexts,
            vap=vap, 
            db=db,
            redis_client=redis_client, 
            vector_store=vector_store, 
            app_state=app_state

        )
        
        # --- 3. PROCESAR RESULTADO Y GESTIONAR ESTADO ---
        final_bot_response = handler_result.get("response")
        metadata_response = handler_result.get("metadata", {})
        log.update(handler_result.get("log", {}))
        
        # Corrección 2: Llamada a la función de guardado con todos sus parámetros
        await save_conversation_state_async(
            redis_client, s_id, handler_result.get("next_state"), handler_result.get("next_params")
        )

    except AuthRequiredError as auth_exc:
        log.update(auth_exc.payload)
        final_bot_response = log.get("bot_response")
        metadata_response = log.get("metadata_details_json", {})
    
    except Exception as e:
        traceback.print_exc()
        handoff = await _handle_human_handoff(req.user_dni or s_id, question)
        log.update({"error_message": f"Error: {e.__class__.__name__} - {e}", "bot_response": handoff.get("response_text", "Error al procesar.")})
        final_bot_response = log["bot_response"]
        metadata_response = {"error_type": e.__class__.__name__, "handoff_ticket": handoff.get("ticket_id")}
        # Intentamos limpiar el estado de redis
        await save_conversation_state_async(redis_client, s_id, None, None)
        
    finally:
        log.update({"bot_response": final_bot_response, "response_time_ms": int((time.time() - start_time) * 1000)})
        
        if not isinstance(metadata_response, dict): metadata_response = {}
        if "intent" not in metadata_response and log.get("intent"): metadata_response["intent"] = log.get("intent")
            
        try:
            log_to_save = log.copy()
            log_to_save["metadata_details_json"] = json.dumps(metadata_response, default=str)
            
            await create_interaction_log_async(db, log_to_save)
            
            if "error_message" not in log:
                await history.add_messages_async([HumanMessage(content=question), AIMessage(content=final_bot_response)])

        except Exception as final_e:
            print(f"CRITICAL: Fallo al guardar log/historial en 'finally': {final_e}")
            traceback.print_exc()

    return ChatResponse(
        session_id=s_id,
        original_message=question,
        bot_response=final_bot_response.strip() if final_bot_response else "No se pudo generar una respuesta.",
        metadata_details_json=metadata_response
    )