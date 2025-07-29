# app/api/endpoints/chat_api_endpoints.py

import time
import traceback
import asyncio
from typing import Dict, Any, List, Optional
import json
from operator import itemgetter
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# --- LangChain Imports ---
from langchain_core.messages import HumanMessage, AIMessage, get_buffer_string
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.documents import Document as LangchainCoreDocument
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_postgres.vectorstores import PGVector

# --- Local Application Imports ---
# ### CAMBIO CLAVE ###: Importamos las nuevas dependencias.
from app.api.dependencies import get_crud_db, get_vector_store, get_app_state
from app.core.app_state import AppState

from app.models.api_client import ApiClient as ApiClientModel
from app.models.context_definition import ContextDefinition, ContextMainType
from app.models.virtual_agent_profile import VirtualAgentProfile
from app.schemas.schemas import ChatRequest, ChatResponse
from app.crud import create_interaction_log, crud_virtual_agent_profile, crud_llm_model_config
from app.config import settings
from app.security.api_key_auth import get_validated_api_client
from ._chat_history_logic import FullyCustomChatMessageHistory
from app.services import cache_service # Asumiendo que cache_service ya usa el nuevo aioredis
from app.tools.sql_tools import run_db_query_chain

from redis.asyncio import Redis as AsyncRedis

# (Tu router y constantes globales van aquí)

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

# --- Constantes y Helpers ---
CONV_STATE_AWAITING_NAME = "awaiting_name_confirmation"
CONV_STATE_AWAITING_TOOL_PARAMS = "awaiting_tool_parameters"
MAX_CLARIFICATION_ATTEMPTS = 2

# Cerca del inicio de chat_api_endpoints.py

# --- EXCEPCIÓN PERSONALIZADA PARA FLUJO DE CONTROL ---
class AuthRequiredError(Exception):
    """Excepción especial para indicar que se requiere login."""
    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload
        super().__init__("Authentication is required for this action.")

async def _handle_human_handoff(uid: str, q: str) -> Dict[str, str]:
    ticket_id = f"TICKET-{int(time.time())}"
    return {"ticket_id": ticket_id, "response_text": f"He creado un ticket de soporte ({ticket_id})."}
# --- HANDLERS DEDICADOS A CASOS DE USO ---



# --- GRUPO 3: GESTIÓN DE ESTADO (REDIS) ---
def _get_conversation_state_key(session_id: str) -> str:
    """Devuelve la clave estandarizada para el NOMBRE del estado de la conversación."""
    return f"conv:state:{session_id}"

def _get_tool_params_key(session_id: str) -> str:
    """Devuelve la clave estandarizada para los PARÁMETROS PARCIALES de la herramienta."""
    return f"conv:params:{session_id}"

async def get_conversation_state_async(
    redis_client: Optional[AsyncRedis], session_id: str
) -> Dict[str, Any]:
    state_key = f"conv:state:{session_id}"
    params_key = f"conv:params:{session_id}"
    
    state, params = await asyncio.gather(
        cache_service.get_generic_cache_async(redis_client, state_key),
        cache_service.get_generic_cache_async(redis_client, params_key)
    )
    
    return {
        "state_name": state if isinstance(state, str) else None,
        "partial_parameters": params if isinstance(params, dict) else {}
    }
    
# --- ORQUESTADOR FINAL (REEMPLAZA TU VERSIÓN ACTUAL POR ESTA VERSIÓN COMPLETA) ---
async def save_conversation_state_async(
    redis_client: Optional[AsyncRedis], 
    session_id: str, 
    state_name: Optional[str], 
    partial_params: Optional[Dict[str, Any]], 
    ttl_seconds: int = 300
):
    """(ASÍNCRONO) Guarda o limpia el estado de la conversación en Redis."""
    state_key = f"conv:state:{session_id}"
    params_key = f"conv:params:{session_id}"

    if state_name is None:
        print(f"STATE_MANAGER: Limpiando estado para la sesión {session_id}")
        # Usamos asyncio.gather para ejecutar las dos llamadas en paralelo
        await asyncio.gather(
            cache_service.delete_generic_cache_async(redis_client, state_key),
            cache_service.delete_generic_cache_async(redis_client, params_key)
        )
    else:
        print(f"STATE_MANAGER: Guardando estado '{state_name}' para la sesión {session_id} con TTL {ttl_seconds}s")
        tasks = [cache_service.set_generic_cache_async(redis_client, state_key, state_name, ttl_seconds=ttl_seconds)]
        if partial_params:
            tasks.append(cache_service.set_generic_cache_async(redis_client, params_key, partial_params, ttl_seconds=ttl_seconds))
        await asyncio.gather(*tasks)


# --- GRUPO 4: CLASIFICADOR DE INTENCIÓN ---
STRUCTURED_CODE_PATTERN = re.compile(r'\b([A-Z]{1,2}\d{3,}|[A-Z]{2,}\d{2,}|(20\d{2})-?\d?)\b', re.IGNORECASE)



# Ahora, reemplaza la función get_user_intent por esta versión con SUPER-LOGGING
async def master_router_agent(
    question: str,
    has_db_capability: bool,
    has_doc_capability: bool,
    llm: BaseChatModel
) -> str:
    """
    Decide qué herramienta usar (RAG vs BD) basado en descripciones, no en clasificación.
    Devuelve 'DOCUMENT_RETRIEVER' o 'DATABASE_TOOL'.
    """
    if not has_db_capability and not has_doc_capability: return "NO_CAPABILITY"
    if has_db_capability and not has_doc_capability: return "DATABASE_TOOL"
    if has_doc_capability and not has_db_capability: return "DOCUMENT_RETRIEVER"
    
    # Si ambas capacidades existen, el LLM decide.
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Eres un agente enrutador experto. Tu única tarea es seleccionar la herramienta más adecuada para responder la pregunta del usuario. "
         "Responde únicamente con el nombre de la herramienta elegida en formato JSON.\n\n"
         "Herramientas Disponibles:\n"
         "1. `DOCUMENT_RETRIEVER`: Úsala para preguntas generales, conceptuales, o teóricas que se pueden responder desde documentos de un curso. "
         "Ejemplos: '¿qué son las ecuaciones lineales?', 'explícame los logaritmos', '¿cuáles son los temas del examen?'.\n\n"
         "2. `DATABASE_TOOL`: Úsala para preguntas que piden datos específicos y personales del usuario, como notas, promedios, horarios o listas. "
         "Ejemplos: 'quiero saber mis notas de mate1', '¿cuál es mi promedio?', 'dame mi horario del ciclo 20241'."),
        ("human", "Pregunta del usuario: {question}\n\nRespuesta JSON (solo la clave 'tool_to_use'):"),
    ])
    
    # Usamos JsonOutputParser para asegurarnos de obtener un JSON válido
    chain = prompt | llm | JsonOutputParser()
    
    try:
        response = await chain.ainvoke({"question": question})
        selected_tool = response.get("tool_to_use")
        if selected_tool in ["DOCUMENT_RETRIEVER", "DATABASE_TOOL"]:
            print(f"MASTER_ROUTER: Herramienta seleccionada: {selected_tool}")
            return selected_tool
    except Exception as e:
        print(f"MASTER_ROUTER: Error al seleccionar herramienta: {e}. Usando fallback.")

    # Fallback muy simple si el LLM falla
    return "DOCUMENT_RETRIEVER"

# --- GRUPO 5: HANDLERS DE CASOS DE USO (LOS TRABAJADORES) ---
# El corazón de la lógica de negocio. Dependen de las funciones de estado y de intención.
# Su orden entre ellos no importa, pero tenerlos agrupados es clave.

async def handle_greeting(vap: VirtualAgentProfile, llm: BaseChatModel, req: ChatRequest) -> Dict[str, Any]:
    """Maneja el saludo inicial de la conversación."""
    log = {"intent": "GREETING"}
    chain = ChatPromptTemplate.from_template(vap.greeting_prompt) | llm | StrOutputParser()
    final_bot_response = await chain.ainvoke({"user_name": req.user_name or "Usuario"})
    
    # Preparamos el siguiente estado si es necesario
    next_state, next_params = None, None
    if vap.name_confirmation_prompt:
        next_state = CONV_STATE_AWAITING_NAME
        next_params = {}
        
    return {"response": final_bot_response, "metadata": {}, "log": log, "next_state": next_state, "next_params": next_params}



async def handle_name_confirmation(question: str, vap: VirtualAgentProfile, llm: BaseChatModel) -> Dict[str, Any]:
    """Maneja la confirmación del nombre del usuario."""
    log = {"intent": "NAME_CONFIRMATION"}
    chain = ChatPromptTemplate.from_template(vap.name_confirmation_prompt) | llm | StrOutputParser()
    final_bot_response = await chain.ainvoke({"user_provided_name": question.strip()})
    
    # Siempre se limpia el estado después de este paso
    return {"response": final_bot_response, "metadata": {}, "log": log, "next_state": None, "next_params": None}


async def handle_tool_clarification(
    req: ChatRequest, conversation_state: Dict, llm: BaseChatModel, history_list: List, 
    active_contexts: List[ContextDefinition]
) -> Dict[str, Any]:
    """Maneja un turno en el bucle de clarificación de una herramienta."""
    ctx_id_from_state = conversation_state["partial_parameters"].get("context_id")
    target_context = next((c for c in active_contexts if c.id == ctx_id_from_state), None)
    if not target_context: raise ValueError(f"Error crítico: No se pudo recargar el contexto {ctx_id_from_state} desde el estado.")
        
    tool_call_result = await run_db_query_chain(
        question=req.message, chat_history_str=get_buffer_string(history_list),
        db_conn_config=target_context.db_connection_config,
        processing_config=target_context.processing_config or {},
        llm=llm, user_dni=req.user_dni, 
        partial_params_from_redis=conversation_state["partial_parameters"]
    )
    
    final_bot_response = tool_call_result.get("final_answer")
    metadata = tool_call_result.get("metadata", {})
    log = {"intent": tool_call_result.get("intent")}

    # Decidimos el siguiente estado basado en el resultado de la herramienta
    next_state, next_params = None, None
    if tool_call_result.get("intent") == "CLARIFICATION_REQUIRED":
        next_state = CONV_STATE_AWAITING_TOOL_PARAMS
        next_params = metadata.get("partial_parameters", {})
        # Adjuntamos el context_id para la siguiente ronda
        next_params["context_id"] = target_context.id
    
    return {"response": final_bot_response, "metadata": metadata, "log": log, "next_state": next_state, "next_params": next_params}

# --- REEMPLAZA TU FUNCIÓN handle_new_question ENTERA POR ESTA VERSIÓN FINAL ---


async def handle_rag_documental(
    req: ChatRequest,
    llm: BaseChatModel,
    history_list: List,
    active_doc_ctx: ContextDefinition,
    vap: VirtualAgentProfile,
    vector_store: PGVector  # <-- ¡Se recibe como parámetro!
) -> Dict[str, Any]:
    """Maneja una pregunta usando RAG sobre documentos."""
    print("ROUTER: Enrutado a DOCUMENT_RETRIEVER. Iniciando flujo RAG.")
    
    # El "calentador de conexión" ya no es necesario aquí. El lifespan lo hizo al arrancar.

    # Definimos la cadena RAG de forma clara
    condense_q_prompt = PromptTemplate.from_template(settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE)
    answer_prompt = ChatPromptTemplate.from_template(vap.system_prompt)
    retriever = vector_store.as_retriever(
        search_kwargs={"k": settings.MAX_RETRIEVED_CHUNKS_RAG, "filter": {"context_name": active_doc_ctx.name}}
    )

    def format_docs(docs: List[LangchainCoreDocument]):
        return "\n\n".join(d.page_content for d in docs)

    # Cadena para generar la pregunta independiente
    standalone_question_chain = RunnablePassthrough.assign(
        chat_history=lambda x: get_buffer_string(history_list)
    ) | condense_q_prompt | llm | StrOutputParser()

    # Cadena para recuperar los documentos
    retrieved_documents_chain = RunnablePassthrough.assign(
        standalone_question=standalone_question_chain,
    ).assign(
        context_docs=itemgetter("standalone_question") | retriever
    )
    
    # Cadena final que une todo
    final_rag_chain = (
        retrieved_documents_chain
        | RunnablePassthrough.assign(
            question=itemgetter("standalone_question"),
            chat_history=lambda x: get_buffer_string(history_list),
            context=itemgetter("context_docs") | RunnableLambda(format_docs),
        )
        | answer_prompt
        | llm
        | StrOutputParser()
    )

    # Invocamos la cadena
    chain_input = {"question": req.message}
    final_bot_response = await final_rag_chain.ainvoke(chain_input)
    
    # Obtenemos metadatos
    retrieved_data = await retrieved_documents_chain.ainvoke(chain_input)
    source_documents = retrieved_data.get("context_docs", [])
    
    metadata = {
        "intent": "RAG_DOCUMENTAL",
        "source_documents": [{"source": doc.metadata.get("source", "N/A"), "page": doc.metadata.get("page")} for doc in source_documents]
    }
    log = {"intent": "RAG_DOCUMENTAL"}
    
    return {"response": final_bot_response, "metadata": metadata, "log": log, "next_state": None, "next_params": None}


async def handle_new_question(
    req: ChatRequest, llm: BaseChatModel, history_list: List,
    active_contexts: List[ContextDefinition],
    all_allowed_contexts: List[ContextDefinition],
    vap: VirtualAgentProfile, client_settings: Dict[str, Any], db: AsyncSession,
    vector_store: PGVector, app_state: AppState

) -> Dict[str, Any]:
    """
    Maneja una nueva pregunta: Usa el Agente Enrutador, aplica seguridad
    y delega la ejecución a cadenas LCEL robustas y explícitas.
    """
    # 1. IDENTIFICAR POTENCIAL Y ACTIVOS (Esto ya estaba perfecto)
    potential_db_contexts = [c for c in all_allowed_contexts if c.main_type == ContextMainType.DATABASE_QUERY]
    potential_doc_contexts = [c for c in all_allowed_contexts if c.main_type == ContextMainType.DOCUMENTAL]
    active_db_ctx = next((c for c in active_contexts if c.main_type == ContextMainType.DATABASE_QUERY), None)
    active_doc_ctx = next((c for c in active_contexts if c.main_type == ContextMainType.DOCUMENTAL), None)
    
    # 2. LLAMAR AL ENRUTADOR MAESTRO (Esto ya estaba perfecto)
    selected_tool = await master_router_agent(
        req.message,
        has_db_capability=(len(potential_db_contexts) > 0),
        has_doc_capability=(len(potential_doc_contexts) > 0),
        llm=llm
    )
    
    # --- 3. EJECUTAR LA HERRAMIENTA SELECCIONADA ---
    
    # CASO A: Herramienta de Base de Datos (Esto ya estaba perfecto)
    if selected_tool == "DATABASE_TOOL":
        if not active_db_ctx:
            print("SECURITY_GATE: AUTH_REQUIRED para DATABASE_TOOL.")
            raise AuthRequiredError({ "intent": "AUTH_REQUIRED", "bot_response": "Para esta consulta, necesito que inicies sesión.", "metadata_details_json": {"action_required": "request_login"} })
        
        print("ROUTER: Enrutado a DATABASE_TOOL. Iniciando flujo de herramienta.")
        tool_call_result = await run_db_query_chain(
            question=req.message, chat_history_str=get_buffer_string(history_list),
            db_conn_config=active_db_ctx.db_connection_config, processing_config=active_db_ctx.processing_config or {},
            llm=llm, user_dni=req.user_dni)
        
        final_bot_response = tool_call_result.get("final_answer")
        metadata = tool_call_result.get("metadata", {})
        log = {"intent": tool_call_result.get("intent")}
        next_state, next_params = (CONV_STATE_AWAITING_TOOL_PARAMS, {**metadata.get("partial_parameters", {}), "context_id": active_db_ctx.id}) if tool_call_result.get("intent") == "CLARIFICATION_REQUIRED" else (None, None)
        
        return {"response": final_bot_response, "metadata": metadata, "log": log, "next_state": next_state, "next_params": next_params}

    # CASO B: RAG documental (¡LA VERSIÓN FINAL, ROBUSTA Y CORRECTA!)
    elif selected_tool == "DOCUMENT_RETRIEVER" and active_doc_ctx:
        print("ROUTER: Enrutado a DOCUMENT_RETRIEVER. Iniciando flujo RAG de Producción.")
        log = {"intent": "RAG_DOCUMENTAL"}
        condense_q_prompt = PromptTemplate.from_template(settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE)
        answer_prompt = ChatPromptTemplate.from_template(vap.system_prompt)
        vector_store = await app_state.get_vector_store(db, active_doc_ctx.id)  # Aseguramos que usamos el vector store correcto
        retriever = vector_store.as_retriever(search_kwargs={"k": 4, "filter": {"context_name": active_doc_ctx.name}})

        def format_docs(docs: List[LangchainCoreDocument]):
            return "\n\n".join(d.page_content for d in docs)

        standalone_question_chain = RunnablePassthrough.assign(
            chat_history=lambda x: get_buffer_string(history_list)
        ) | condense_q_prompt | llm | StrOutputParser()

        retrieved_documents_chain = RunnablePassthrough.assign(
            standalone_question=standalone_question_chain,
        ).assign(
            context_docs=itemgetter("standalone_question") | retriever
        )
        
        final_rag_chain = (
            retrieved_documents_chain
            | RunnablePassthrough.assign(
                # ¡LA CURA FINAL! Nos aseguramos de que la clave 'question' siempre exista
                question=itemgetter("standalone_question"),
                chat_history=lambda x: get_buffer_string(history_list),
                context=itemgetter("context_docs") | RunnableLambda(format_docs),
            )
            | answer_prompt
            | llm
            | StrOutputParser()
        )

        chain_input = {"question": req.message}
        final_bot_response = await final_rag_chain.ainvoke(chain_input)
        
        retrieved_data = await retrieved_documents_chain.ainvoke(chain_input)
        source_documents = retrieved_data.get("context_docs", [])
        
        metadata = {
            "intent": "RAG_DOCUMENTAL",
            "source_documents": [{"source": doc.metadata.get("source", "N/A"), "page": doc.metadata.get("page")} for doc in source_documents]
        }
        
        return {"response": final_bot_response, "metadata": metadata, "log": log, "next_state": None, "next_params": None}
    
    # CASO C: Fallback
    else:
        log = {"intent": "NO_CAPABILITY"}
        return {"response": "Lo siento, no tengo las herramientas o documentos necesarios.", "metadata": {"intent": "NO_CAPABILITY"}, "log": log, "next_state": None, "next_params": None}

# --- GRUPO 6: EL ENRUTADOR ---
# Esta función DEBE ir DESPUÉS de todos los handlers, porque los llama.
async def route_request(
    req: ChatRequest, conversation_state: Dict, llm: BaseChatModel, history_list: List,
    active_contexts: List[ContextDefinition], # <<<--- RECIBE LOS ACTIVOS
    all_allowed_contexts: List[ContextDefinition], # <<<--- Y EL POTENCIAL TOTAL
    vap: VirtualAgentProfile,
    client_settings: Dict[str, Any], db: AsyncSession, vector_store: PGVector, app_state: AppState
) -> Dict[str, Any]:
    """
    Toma el estado de la conversación y la pregunta, y elige el handler correcto.
    """
    current_state = conversation_state["state_name"]
    question = req.message
    
    # 1. ¿Hay un saludo inicial?
    if not history_list and question == "__INICIAR_CHAT__":
        return await handle_greeting(vap, llm, req)
        
    # 2. ¿Estamos en medio de un estado de conversación?
    if current_state == CONV_STATE_AWAITING_NAME:
        return await handle_name_confirmation(question, vap, llm)
    
    if current_state == CONV_STATE_AWAITING_TOOL_PARAMS:
        return await handle_tool_clarification(req, conversation_state, llm, history_list, active_contexts)
    
    if current_state is None:    
        return await handle_new_question(
        req=req,llm=llm,history_list=history_list,
        active_contexts=active_contexts,
        all_allowed_contexts=all_allowed_contexts,
        vap=vap,  # <<< --- AÑADE ESTE ARGUMENTO
        client_settings=client_settings, # <<< --- ASEGÚRATE DE QUE SE PASA AQUÍ
        db=db,
        vector_store=vector_store,  # <<< --- Y AQUÍ
        app_state=app_state  # <<< --- Y AQUÍ
    )

    # 3. Si no hay estado, es una pregunta nueva.
    return await handle_new_question(req, llm, history_list, active_contexts,
        all_allowed_contexts, vap, client_settings, db)


# Coloca esto después de los imports y antes de tus otras funciones 'handle_...'


# --- FUNCIONES DE GESTIÓN DE ESTADO ---




async def save_conversation_state_async(
    redis_client: Optional[AsyncRedis], 
    session_id: str, 
    state_name: Optional[str], 
    partial_params: Optional[Dict[str, Any]], 
    ttl_seconds: int = 300
):
    """(ASÍNCRONO) Guarda o limpia el estado de la conversación en Redis."""
    state_key = f"conv:state:{session_id}"
    params_key = f"conv:params:{session_id}"

    if state_name is None:
        print(f"STATE_MANAGER: Limpiando estado para la sesión {session_id}")
        # Usamos asyncio.gather para ejecutar las dos llamadas en paralelo
        await asyncio.gather(
            cache_service.delete_generic_cache_async(redis_client, state_key),
            cache_service.delete_generic_cache_async(redis_client, params_key)
        )
    else:
        print(f"STATE_MANAGER: Guardando estado '{state_name}' para la sesión {session_id} con TTL {ttl_seconds}s")
        tasks = [cache_service.set_generic_cache_async(redis_client, state_key, state_name, ttl_seconds=ttl_seconds)]
        if partial_params:
            tasks.append(cache_service.set_generic_cache_async(redis_client, params_key, partial_params, ttl_seconds=ttl_seconds))
        await asyncio.gather(*tasks)


@router.post("/", response_model=ChatResponse)
async def process_chat_message(
    req: ChatRequest,
    client: ApiClientModel = Depends(get_validated_api_client),
    # ### CAMBIO CLAVE ###: Inyectamos las dependencias aquí
    db: AsyncSession = Depends(get_crud_db),
    vector_store: PGVector = Depends(get_vector_store),
    app_state: AppState = Depends(get_app_state)
):
    start_time, question, s_id = time.time(), req.message, req.session_id
    log: Dict[str, Any] = {"user_dni": req.user_dni or s_id, "api_client_name": client.name, "user_message": question}
    history = FullyCustomChatMessageHistory(s_id)
    final_bot_response, metadata_response = "Lo siento, ha ocurrido un error.", {}

    try:
        # --- 1. CARGA DE DEPENDENCIAS ---
        api_client_settings = client.settings or {}
        allowed_ctx_ids = api_client_settings.get("allowed_context_ids", [])
        if not allowed_ctx_ids:
            raise HTTPException(403, "API Key sin contextos.")

        stmt_base = select(ContextDefinition).where(ContextDefinition.id.in_(allowed_ctx_ids), ContextDefinition.is_active == True)
        all_allowed_contexts_stmt = select(ContextDefinition).where(
            ContextDefinition.id.in_(allowed_ctx_ids), ContextDefinition.is_active == True
        ).options(selectinload(ContextDefinition.db_connection_config))
        all_allowed_contexts = (await db.execute(all_allowed_contexts_stmt)).scalars().unique().all()


        if req.is_authenticated_user:
            active_contexts = (await db.execute(
                stmt_base.options(selectinload(ContextDefinition.db_connection_config))
            )).scalars().unique().all()
        else:
            active_contexts = (await db.execute(
                stmt_base.filter(ContextDefinition.is_public == True)
                .options(selectinload(ContextDefinition.db_connection_config))
            )).scalars().unique().all()
            if any(kw in question.lower() for kw in getattr(settings, 'DB_INTENT_KEYWORDS', [])):
                q_private = select(func.count()).select_from(
                    stmt_base.filter(ContextDefinition.is_public == False, ContextDefinition.main_type == ContextMainType.DATABASE_QUERY).subquery()
                )
                if (await db.execute(q_private)).scalar_one() > 0:
                    raise StopIteration({
                        "intent": "AUTH_REQUIRED", "bot_response": "Para esta consulta, necesito que inicies sesión.",
                        "metadata_details_json": {"action_required": "request_login"}
                    })
        
        if not active_contexts:
            raise HTTPException(404, "No hay contextos válidos para esta solicitud.")
            
        vap_id = api_client_settings.get("default_virtual_agent_profile_id_override") or active_contexts[0].virtual_agent_profile_id
        vap = await crud_virtual_agent_profile.get_fully_loaded_profile(db, vap_id)
        llm_cfg_id = (api_client_settings.get("default_llm_model_config_id_override") or vap.llm_model_config_id or active_contexts[0].default_llm_model_config_id)
        llm_config = await crud_llm_model_config.get_llm_model_config_by_id(db, llm_cfg_id)
        llm = await app_state.get_cached_llm(db, model_config=llm_config)
        history_list = await asyncio.to_thread(history.messages.copy)
        log["llm_model_used"] = llm_config.display_name

        # --- 2. RECUPERAR ESTADO Y DELEGAR AL ENRUTADOR ---
        conversation_state = get_conversation_state_async(s_id)
        req.client_settings = client.settings or {}

        handler_result = await route_request(
            req=req,
            conversation_state=conversation_state,
            llm=llm,
            history_list=history_list,
            active_contexts=active_contexts,
            all_allowed_contexts=all_allowed_contexts,
            vap=vap,
            client_settings=api_client_settings,
            db=db,
            vector_store=vector_store, # <-- Pasamos el vector_store inyectado
            app_state=app_state # <-- Pasamos el estado de la app completo
        )
        
        # --- 3. PROCESAR RESULTADO Y GESTIONAR ESTADO ---
        final_bot_response = handler_result.get("response")
        metadata_response = handler_result.get("metadata", {})
        log.update(handler_result.get("log", {}))
        
        save_conversation_state_async(
            s_id,
            handler_result.get("next_state"),
            handler_result.get("next_params")
        )

    # --- 4. MANEJO DE EXCEPCIONES ---

    except AuthRequiredError as auth_exc:
        update = auth_exc.payload or {}
        log.update(update)
        final_bot_response = log.get("bot_response")
        metadata_response = log.get("metadata_details_json", {})
    
    except Exception as e: # El genérico ahora es el último recurso
        traceback.print_exc()
        handoff = await _handle_human_handoff(req.user_dni or s_id, question)
        log.update({
            "error_message": f"Error: {e.__class__.__name__} - {e}",
            "bot_response": handoff.get("response_text", "Error al procesar.")
        })
        final_bot_response = log["bot_response"]
        metadata_response = {"error_type": e.__class__.__name__, "handoff_ticket": handoff.get("ticket_id")}
        save_conversation_state_async(s_id, None, None)
        
    finally:
        log.update({
            "bot_response": final_bot_response,
            "response_time_ms": int((time.time() - start_time) * 1000)
        })
        
        # Unificamos la lógica de los metadatos aquí para asegurar que siempre existan.
        if not isinstance(metadata_response, dict):
            metadata_response = {}
            
        # <<< --- LÓGICA DE METADATOS EN TODAS LAS RESPUESTAS --- >>>
        # Si la intención principal no está en los metadatos, la añadimos.
        if "intent" not in metadata_response and log.get("intent"):
            metadata_response["intent"] = log.get("intent")
            
        try:
            # Usamos la misma variable para el log y para el historial
            log_to_save = log.copy()
            log_to_save["metadata_details_json"] = json.dumps(metadata_response, default=str)
            
            await create_interaction_log(db, log_to_save)
            
            if log.get("bot_response") and not log.get("error_message"):
                await asyncio.to_thread(
                    history.add_messages,
                    [HumanMessage(content=question), AIMessage(content=final_bot_response)]
                )
        except Exception as final_e:
            print(f"CRITICAL: Fallo al guardar log/historial: {final_e}")
            traceback.print_exc()

    return ChatResponse(
        session_id=s_id,
        original_message=question,
        bot_response=final_bot_response.strip() if final_bot_response else "No se pudo generar una respuesta.",
        metadata_details_json=metadata_response

    )