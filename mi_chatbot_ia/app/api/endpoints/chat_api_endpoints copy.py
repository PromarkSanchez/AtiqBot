# app/api/endpoints/chat_api_endpoints.py (VERSIÓN FINAL Y COMPLETA)

import time, traceback, asyncio, json
from typing import Dict, Any, List, Optional
from operator import itemgetter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from redis.asyncio import Redis as AsyncRedis

from langchain_core.messages import HumanMessage, AIMessage, get_buffer_string
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document as LangchainCoreDocument
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_postgres.vectorstores import PGVector

from app.api.dependencies import get_crud_db, get_vector_store, get_app_state, get_redis_client
from app.core.app_state import AppState
from app.config import settings
from app.security.api_key_auth import get_validated_api_client
from app.services import cache_service
from app.crud import crud_virtual_agent_profile, crud_llm_model_config, create_interaction_log_async
from app.models.api_client import ApiClient as ApiClientModel
from app.models.context_definition import ContextDefinition, ContextMainType
from app.models.virtual_agent_profile import VirtualAgentProfile
from app.schemas.schemas import ChatRequest, ChatResponse
from ._chat_history_logic import FullyCustomChatMessageHistory
from app.tools.sql_tools import run_db_query_chain

router = APIRouter(tags=["Chat"])
CONV_STATE_AWAITING_NAME = "awaiting_name_confirmation"
CONV_STATE_AWAITING_TOOL_PARAMS = "awaiting_tool_parameters"

class AuthRequiredError(Exception):
    def __init__(self, payload: Dict[str, Any]): self.payload = payload; super().__init__("Authentication is required.")

async def _handle_human_handoff(uid: str, q: str) -> Dict[str, str]:
    return {"ticket_id": f"TICKET-{int(time.time())}", "response_text": f"He creado un ticket de soporte."}

def _get_conversation_state_key(s_id: str) -> str: return f"conv:state:{s_id}"
def _get_tool_params_key(s_id: str) -> str: return f"conv:params:{s_id}"

async def get_conversation_state_async(redis: Optional[AsyncRedis], s_id: str) -> Dict[str, Any]:
    if not redis: return {"state_name": None, "partial_parameters": {}}
    state, params = await asyncio.gather(cache_service.get_generic_cache_async(redis, _get_conversation_state_key(s_id)), cache_service.get_generic_cache_async(redis, _get_tool_params_key(s_id)))
    return {"state_name": state, "partial_parameters": params or {}}

async def save_conversation_state_async(redis: Optional[AsyncRedis], s_id: str, state: Optional[str], params: Optional[Dict[str, Any]], ttl: int = 300):
    if not redis: return
    state_k, params_k = _get_conversation_state_key(s_id), _get_tool_params_key(s_id)
    if state is None: await asyncio.gather(cache_service.delete_generic_cache_async(redis, state_k), cache_service.delete_generic_cache_async(redis, params_k))
    else: await asyncio.gather(cache_service.set_generic_cache_async(redis, state_k, state, ttl), cache_service.set_generic_cache_async(redis, params_k, params, ttl))

def keyword_based_ruler(question: str) -> Optional[str]:
    q_lower = question.lower()
    db_k = ["mis notas", "mi nota", "mis calificaciones", "mi promedio", "cuanto saqué", "cuánto me falta", "mi horario", "mis cursos"]
    if any(k in q_lower for k in db_k): return "DATABASE_TOOL"
    end_k = ["gracias", "muchas gracias", "eso es todo", "adiós", "nos vemos", "chao", "cancelar", "ya no deseo"]
    if len(question.split()) <= 5 and any(k in q_lower for k in end_k): return "CONVERSATION_END"
    return None

async def determine_intention(req: ChatRequest) -> str:
    rule_intent = keyword_based_ruler(req.message)
    return rule_intent or "DOCUMENT_RETRIEVER"

async def handle_greeting(vap, llm, req) -> Dict[str, Any]:
    chain = ChatPromptTemplate.from_template(vap.greeting_prompt) | llm | StrOutputParser()
    resp = await chain.ainvoke({"user_name": req.user_name or "Visitante"})
    return {"response": resp, "metadata": {}, "log": {"intent": "GREETING"}, "next_state": CONV_STATE_AWAITING_NAME, "next_params": {}}

async def handle_name_confirmation(q, vap, llm) -> Dict[str, Any]:
    chain = ChatPromptTemplate.from_template(vap.name_confirmation_prompt) | llm | StrOutputParser()
    resp = await chain.ainvoke({"user_provided_name": q.strip()})
    return {"response": resp, "metadata": {}, "log": {"intent": "NAME_CONFIRMATION"}, "next_state": None, "next_params": None}

async def handle_conversation_end(req) -> Dict[str, Any]:
    resp = f"¡De nada, {req.user_name or 'tú'}! Ha sido un placer ayudarte. Si tienes más preguntas, no dudes en volver. ¡Que tengas un excelente día! 🚀"
    return {"response": resp, "metadata": {}, "log": {"intent": "CONVERSATION_END"}, "next_state": None, "next_params": None}

async def handle_new_question(req: ChatRequest, llm: BaseChatModel, history_list: List, active_contexts: List[ContextDefinition], all_allowed_contexts: List[ContextDefinition], vap: VirtualAgentProfile, db: AsyncSession, vector_store: PGVector, app_state: AppState, redis_client: Optional[AsyncRedis]) -> Dict[str, Any]:
    db_ctx, doc_ctx = next((c for c in active_contexts if c.main_type == ContextMainType.DATABASE_QUERY), None), next((c for c in active_contexts if c.main_type == ContextMainType.DOCUMENTAL), None)
    intent = await determine_intention(req)
    
    if intent == "CONVERSATION_END": return await handle_conversation_end(req)
        
    if intent == "DATABASE_TOOL":
        if not req.is_authenticated_user: return {"response": "Para esta consulta, necesito que inicies sesión.", "metadata": {"action_required": "request_login"}, "log": {"intent": "AUTH_REQUIRED"}, "next_state": None, "next_params": None}
        
        initial_params = {"original_question": req.message}
        res = await run_db_query_chain(
            question=req.message, chat_history_str=get_buffer_string(history_list),
            db_conn_config=db_ctx.db_connection_config, processing_config=db_ctx.processing_config or {},
            llm=llm, user_dni=req.user_dni, user_name=req.user_name, partial_params_from_redis=initial_params
        )
        
        next_s, next_p = None, None
        if res.get("intent") == "CLARIFICATION_REQUIRED":
            next_s, next_p = CONV_STATE_AWAITING_TOOL_PARAMS, res.get("metadata", {})
            next_p["context_id"] = db_ctx.id
        return {"response": res.get("final_answer"), "metadata": res.get("metadata", {}), "log": {"intent": res.get("intent")}, "next_state": next_s, "next_params": next_p}
        
    elif intent == "DOCUMENT_RETRIEVER":
        if not doc_ctx: return {"response": "Lo siento, no tengo acceso a documentos para esto.", "metadata":{}, "log": {"intent": "NO_CONTEXT_AVAILABLE"}, "next_state": None, "next_params": None}
        
        recent_hist = history_list[-settings.CHAT_HISTORY_WINDOW_SIZE_RAG:]
        cond_prompt = PromptTemplate.from_template(settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE)
        ans_prompt = ChatPromptTemplate.from_template(vap.system_prompt)
        retriever = vector_store.as_retriever(search_kwargs={"k": settings.MAX_RETRIEVED_CHUNKS_RAG, "filter": {"context_name": doc_ctx.name}})
        def format_docs(docs: List[LangchainCoreDocument]): return "\n\n".join(d.page_content for d in docs)
        
        rewriter_chain = {"question": itemgetter("question"), "chat_history": lambda x: get_buffer_string(x["chat_history"])} | cond_prompt | llm | StrOutputParser()
        rewritten_question = await rewriter_chain.ainvoke({"question": req.message, "chat_history": recent_hist})
        
        docs = await retriever.ainvoke(rewritten_question)
        context_str = format_docs(docs)
        
        rag_chain = ans_prompt | llm.bind(stop=["\nHuman:"]) | StrOutputParser()
        final_response = await rag_chain.ainvoke({"context": context_str, "question": rewritten_question, "chat_history": get_buffer_string(recent_hist)})
        
        metadata = {"source_documents": [{"source": doc.metadata.get("source", "N/A"), "page": doc.metadata.get("page")} for doc in docs]}
        return {"response": final_response, "log": {"intent": "RAG_DOCUMENTAL"}, "metadata": metadata, "next_state": None, "next_params": None}
        
    else: return {"response": "Lo siento, no estoy seguro de cómo ayudarte.", "metadata":{}, "log": {"intent": "NO_CAPABILITY"}, "next_state": None, "next_params": None}

async def handle_tool_clarification(req: ChatRequest, conv_state: Dict, llm: BaseChatModel, hist: List, act_ctx: List[ContextDefinition], vap: VirtualAgentProfile, redis_cli: Optional[AsyncRedis]) -> Dict[str, Any]:
    params_redis = conv_state.get("partial_parameters", {})
    ctx_id = params_redis.get("context_id")
    target_ctx = next((c for c in act_ctx if c.id == ctx_id), None)
    
    if not target_ctx:
        await save_conversation_state_async(redis_cli, req.session_id, None, None)
        return {"response": "Tu sesión ha cambiado. Por favor, intenta de nuevo.", "metadata":{}, "log": {"intent": "AUTH_STATE_CHANGED"}, "next_state": None, "next_params": None}
        
    res = await run_db_query_chain(
        question=req.message, chat_history_str=get_buffer_string(hist),
        db_conn_config=target_ctx.db_connection_config, processing_config=target_ctx.processing_config or {},
        llm=llm, user_dni=req.user_dni, user_name=req.user_name, partial_params_from_redis=params_redis
    )
    
    next_s, next_p = None, None
    if res.get("intent") == "CLARIFICATION_REQUIRED":
        next_s, next_p = CONV_STATE_AWAITING_TOOL_PARAMS, res.get("metadata", {})
        if "context_id" not in next_p: next_p["context_id"] = ctx_id
            
    return {"response": res.get("final_answer"), "metadata": res.get("metadata", {}), "log": {"intent": res.get("intent")}, "next_state": next_s, "next_params": next_p}

async def route_request(req: ChatRequest, conv_state: Dict, llm: BaseChatModel, hist: List, act_ctx: List[ContextDefinition], all_ctx: List[ContextDefinition], vap: VirtualAgentProfile, db: AsyncSession, redis_cli: Optional[AsyncRedis], vec_store: PGVector, app_state: AppState) -> Dict[str, Any]:
    state_name = conv_state.get("state_name")
    
    if not hist and req.message == "__INICIAR_CHAT__": return await handle_greeting(vap, llm, req)
    if len(hist) == 2 and state_name == CONV_STATE_AWAITING_NAME: return await handle_name_confirmation(req.message, vap, llm)
    
    if state_name == CONV_STATE_AWAITING_TOOL_PARAMS:
        intent = await determine_intention(req)
        if intent != "DATABASE_TOOL":
            await save_conversation_state_async(redis_cli, req.session_id, None, None)
            # Pasamos TODOS los argumentos requeridos a handle_new_question
            return await handle_new_question(req, llm, hist, act_ctx, all_ctx, vap, db, vec_store, app_state, redis_cli)
        else:
            # Pasamos TODOS los argumentos requeridos a handle_tool_clarification
            return await handle_tool_clarification(req, conv_state, llm, hist, act_ctx, vap, redis_cli)
    
    # Pasamos TODOS los argumentos requeridos a handle_new_question
    return await handle_new_question(req, llm, hist, act_ctx, all_ctx, vap, db, vec_store, app_state, redis_cli)

@router.post("/api/v1/chat/", response_model=ChatResponse)
async def process_chat_message(
    req: ChatRequest, client: ApiClientModel = Depends(get_validated_api_client), db: AsyncSession = Depends(get_crud_db),
    app_state: AppState = Depends(get_app_state), redis_client: Optional[AsyncRedis] = Depends(get_redis_client),
    vector_store: PGVector = Depends(get_vector_store)
):
    start_time, question, s_id = time.time(), req.message, req.session_id
    log, final_bot_response, metadata_response = {"user_dni": req.user_dni or s_id, "api_client_name": client.name, "user_message": question}, "Lo siento, ha ocurrido un error.", {}
    history = FullyCustomChatMessageHistory(s_id, redis_client=redis_client)
    try:
        api_settings, allowed_ids = (client.settings or {}), (client.settings or {}).get("allowed_context_ids", [])
        if not allowed_ids: raise HTTPException(403, "API Key sin contextos.")
        
        stmt = select(ContextDefinition).where(ContextDefinition.id.in_(allowed_ids), ContextDefinition.is_active == True)
        all_ctx = (await db.execute(stmt.options(selectinload(ContextDefinition.db_connection_config)))).scalars().unique().all()
        act_ctx = all_ctx if req.is_authenticated_user else [c for c in all_ctx if c.is_public]
        if not act_ctx: raise HTTPException(404, "No hay contextos válidos.")
            
        vap_id = api_settings.get("default_virtual_agent_profile_id_override") or act_ctx[0].virtual_agent_profile_id
        vap = await crud_virtual_agent_profile.get_fully_loaded_profile(db, vap_id)
        llm_cfg_id = (api_settings.get("default_llm_model_config_id_override") or vap.llm_model_config_id or act_ctx[0].default_llm_model_config_id)
        llm_config = await crud_llm_model_config.get_llm_model_config_by_id(db, llm_cfg_id)
        if not llm_config: raise HTTPException(404, "LLM Config no encontrada.")
        
        temp = 0.7
        if llm_config.default_temperature is not None: temp = llm_config.default_temperature
        if hasattr(vap, 'temperature_override') and vap.temperature_override is not None: temp = vap.temperature_override
        
        llm = await app_state.get_cached_llm(model_config=llm_config, temperature_to_use=temp)
        hist = await history.get_messages_async()
        log["llm_model_used"] = llm_config.display_name
        conv_state = await get_conversation_state_async(redis_client, s_id)

        res = await route_request(req, conv_state, llm, hist, act_ctx, all_ctx, vap, db, redis_client, vector_store, app_state)
        
        final_bot_response, metadata_response = res.get("response"), res.get("metadata", {})
        log.update(res.get("log", {}))
        await save_conversation_state_async(redis_client, s_id, res.get("next_state"), res.get("next_params"))
    
    except AuthRequiredError as auth_exc:
        payload = auth_exc.payload
        final_bot_response, metadata_response = payload.get("bot_response", "Se requiere autenticación."), payload.get("metadata_details_json", {})
        log.update(payload)
    except Exception as e:
        traceback.print_exc()
        handoff = await _handle_human_handoff(req.user_dni or s_id, question)
        log.update({"error_message": f"{e.__class__.__name__}: {e}", "bot_response": handoff.get("response_text", "Error.")})
        final_bot_response, metadata_response = log["bot_response"], {"error_type": e.__class__.__name__, "handoff_ticket": handoff.get("ticket_id")}
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
            print(f"CRITICAL: Fallo al guardar log/historial: {final_e}")
            traceback.print_exc()
    
    return ChatResponse(session_id=s_id, original_message=question, bot_response=final_bot_response.strip() if final_bot_response else "", metadata_details_json=metadata_response)