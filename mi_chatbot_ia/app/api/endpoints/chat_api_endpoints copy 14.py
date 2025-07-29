# app/api/endpoints/chat_api_endpoints.py

import time
import traceback
import asyncio
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func  ### CAMBIO 1: Asegurarnos de importar 'func' para 'func.count()' ###
from sqlalchemy.orm import selectinload

# Langchain Imports (estilo moderno LCEL)
from langchain_core.messages import HumanMessage, AIMessage, get_buffer_string
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document as LangchainCoreDocument

# Módulos de la Aplicación (unificados)
from app.db.session import get_crud_db_session
from app.models.api_client import ApiClient as ApiClientModel
from app.models.context_definition import ContextDefinition, ContextMainType
from app.models.virtual_agent_profile import VirtualAgentProfile
from app.schemas.schemas import ChatRequest, ChatResponse
from app.crud import create_interaction_log, crud_virtual_agent_profile, crud_llm_model_config
from app.config import settings
from app.security.api_key_auth import get_validated_api_client
from app.core.app_state import get_sync_vector_store, get_cached_llm_adapter
from ._chat_history_logic import FullyCustomChatMessageHistory
from app.services import cache_service
from app.tools.sql_tools import run_text_to_sql_lcel_chain
from app.tools.sql_tools import run_db_query_chain

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

# Constantes para los estados de la conversación.
CONV_STATE_AWAITING_NAME = "awaiting_name_confirmation"

async def _handle_human_handoff(user_identifier: str, question: str) -> Dict[str, str]:
    ticket_id = f"TICKET-{int(time.time())}"
    response_text = f"He creado un ticket de soporte ({ticket_id}). Un agente se pondrá en contacto contigo para resolver tu consulta."
    return {"ticket_id": ticket_id, "response_text": response_text}

@router.post("/", response_model=ChatResponse)
async def process_chat_message(
    chat_request: ChatRequest,
    db_crud: AsyncSession = Depends(get_crud_db_session),
    current_api_client: ApiClientModel = Depends(get_validated_api_client)
):
    start_time = time.time()
    question = chat_request.message
    session_id = chat_request.session_id
    user_log_identifier = chat_request.user_dni if chat_request.is_authenticated_user else session_id
    
    ### CAMBIO 2: Inicializar todas las variables críticas fuera del 'try' para evitar UnboundLocalError ###
    log_entry_data: Dict[str, Any] = {
        "user_dni": user_log_identifier, "api_client_name": current_api_client.name, "user_message": question,
        "llm_model_used": "N/A", "bot_response": "[Error de procesamiento]", "intent": "UNKNOWN",
        "metadata_details_json": {}, "error_message": None, "retrieved_context_summary": None,
    }
    history_manager = FullyCustomChatMessageHistory(session_id=session_id)
    final_bot_response = ""
    
    try:
        api_client_settings = current_api_client.settings or {}
        allowed_context_ids = api_client_settings.get("allowed_context_ids", [])
        if not allowed_context_ids:
            raise HTTPException(403, "Esta API Key no tiene contextos de conocimiento asociados.")

        ### CAMBIO 3: Nueva lógica de obtención y validación de contextos ###
        # Esta sección ahora maneja el caso de "necesita login" en lugar de fallar.
        stmt_base = select(ContextDefinition).where(
            ContextDefinition.id.in_(allowed_context_ids),
            ContextDefinition.is_active == True
        )
        
        active_contexts: List[ContextDefinition]
        
        if chat_request.is_authenticated_user:
            # Usuario autenticado: Obtiene todos los contextos activos (públicos y privados).
            result = await db_crud.execute(stmt_base)
            active_contexts = result.scalars().all()
        else:
            # Usuario invitado: Intenta obtener solo los contextos públicos.
            public_contexts_query = stmt_base.filter(ContextDefinition.is_public == True)
            result = await db_crud.execute(public_contexts_query)
            active_contexts = result.scalars().all()
            
            # Si un invitado no encontró un contexto público... ¿debería loguearse?
            if not active_contexts:
                private_contexts_for_this_key_query = stmt_base.filter(ContextDefinition.is_public == False)
                count_result = await db_crud.execute(select(func.count()).select_from(private_contexts_for_this_key_query.subquery()))
                
                # Si existen contextos privados para esta API Key que el usuario podría usar.
                if count_result.scalar_one() > 0:
                    log_entry_data["intent"] = "AUTH_REQUIRED_PROMPT"
                    final_bot_response = (
                        "Para responder a tu pregunta, necesito que inicies sesión. "
                        "Así puedo darte una respuesta completa y segura."
                    )
                    log_entry_data["metadata_details_json"] = {"action_required": "request_login"}
                    log_entry_data["bot_response"] = final_bot_response

                    # Usamos 'raise StopIteration' para cortar el flujo y pasar al 'finally' limpiamente.
                    raise StopIteration("Usuario invitado requiere login para acceder a contexto privado.")

        # Si después de toda la lógica, no hay contextos, es un error definitivo.
        if not active_contexts:
            raise HTTPException(404, "Lo siento, no tengo información disponible sobre ese tema para tu nivel de acceso.")
        
        # ### FIN DE LA SECCIÓN DE CAMBIOS CLAVE ###
        
        # De aquí en adelante, el código es el mismo que tenías, porque ahora opera sobre la lista
        # `active_contexts` que ya ha sido filtrada correctamente.

        chat_history_list = await asyncio.to_thread(lambda: history_manager.messages)
        has_history = len(chat_history_list) > 0

        if not has_history and question != "__INICIAR_CHAT__":
            cached_response = cache_service.get_cached_response(current_api_client.id, [c.id for c in active_contexts], question)
            if cached_response:
                log_entry_data.update({"llm_model_used": "CACHE", "intent": "CACHE_HIT", **cached_response})
                raise StopIteration("Respuesta encontrada en caché.")
        
        vap_id = api_client_settings.get("default_virtual_agent_profile_id_override") or active_contexts[0].virtual_agent_profile_id
        agent_profile = await crud_virtual_agent_profile.get_fully_loaded_profile(db_crud, vap_id)
        if not agent_profile: raise ValueError(f"Perfil de Agente Válido (ID: {vap_id}) no encontrado.")
        
        llm_config_id = api_client_settings.get("default_llm_model_config_id_override") or agent_profile.llm_model_config_id
        llm_config = await crud_llm_model_config.get_llm_model_config_by_id(db_crud, llm_config_id)
        if not llm_config: raise ValueError(f"Modelo LLM Válido (ID: {llm_config_id}) no encontrado.")

        llm = await get_cached_llm_adapter(db_crud, model_config=llm_config)
        log_entry_data["llm_model_used"] = llm_config.display_name

        final_bot_response = ""
        current_conv_state = cache_service.get_cache(f"chat_state:{session_id}")
    
        # ETAPA 1: Saludo inicial
        if not has_history and question == "__INICIAR_CHAT__":
            log_entry_data["intent"] = "GREETING_STAGE"
            if not agent_profile.greeting_prompt: raise ValueError("Agente sin 'greeting_prompt'.")
            chain = ChatPromptTemplate.from_template(agent_profile.greeting_prompt) | llm | StrOutputParser()
            final_bot_response = await chain.ainvoke({"user_name": chat_request.user_name or "Usuario"})
            if agent_profile.name_confirmation_prompt:
                cache_service.set_cache(f"chat_state:{session_id}", CONV_STATE_AWAITING_NAME, ttl_seconds=300)

        # ETAPA 2: Confirmación de Nombre
        elif current_conv_state == CONV_STATE_AWAITING_NAME and agent_profile.name_confirmation_prompt:
            log_entry_data["intent"] = "NAME_CONFIRMATION_STAGE"
            chain = ChatPromptTemplate.from_template(agent_profile.name_confirmation_prompt) | llm | StrOutputParser()
            user_name_from_input = question.strip()
            cache_service.set_cache(f"user_name:{session_id}", user_name_from_input, ttl_seconds=settings.CACHE_EXPIRATION_SECONDS)
            final_bot_response = await chain.ainvoke({"user_provided_name": user_name_from_input})
            cache_service.delete_cache(f"chat_state:{session_id}")

        # ETAPA 3: Resolución de Consulta (RAG/SQL)
        else:
            is_sql_intent = any(kw.lower() in question.lower() for kw in settings.SQL_INTENT_KEYWORDS)
            target_context = next((c for c in active_contexts if c.main_type == ContextMainType.DATABASE_QUERY and is_sql_intent),
                                next((c for c in active_contexts if c.main_type == ContextMainType.DOCUMENTAL), active_contexts[0]))

            if target_context.main_type == ContextMainType.DOCUMENTAL:
                log_entry_data["intent"] = "RAG_DOCUMENTAL"
                user_name_from_cache = cache_service.get_cache(f"user_name:{session_id}") or chat_request.user_name or "Usuario"
                # (tu lógica interna de run_rag_chain_sync se mantiene exactamente igual)
                def run_rag_chain_sync():
                    condense_question_prompt = PromptTemplate.from_template(settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE)
                    answer_prompt = ChatPromptTemplate.from_template(agent_profile.system_prompt)
                    standalone_question_chain = condense_question_prompt | llm | StrOutputParser()
                    vector_store = get_sync_vector_store()
                    context_names_for_filter = [ctx.name for ctx in active_contexts if ctx.main_type == ContextMainType.DOCUMENTAL]
                    retriever = vector_store.as_retriever(search_kwargs={"k": settings.MAX_RETRIEVED_CHUNKS_RAG, "filter": {"context_name": {"$in": context_names_for_filter}}})
                    def format_docs_and_log(docs: List[LangchainCoreDocument]):
                        unique_metadata, seen_sources = [], set()
                        for doc in docs:
                            source_key = doc.metadata.get("source_filename")
                            if source_key and source_key not in seen_sources:
                                unique_metadata.append(doc.metadata)
                                seen_sources.add(source_key)
                        log_entry_data["metadata_details_json"]["source_documents"] = unique_metadata
                        log_entry_data["retrieved_context_summary"] = "\n".join([f"Doc: {m.get('source_filename', 'N/A')}" for m in unique_metadata[:3]])
                        return "\n\n---\n\n".join(d.page_content for d in docs)
                    conversational_rag_chain = (RunnablePassthrough.assign(standalone_question=RunnablePassthrough.assign(chat_history=lambda x: get_buffer_string(chat_history_list[-settings.CHAT_HISTORY_WINDOW_SIZE_RAG:])) | standalone_question_chain) | RunnablePassthrough.assign(context=lambda x: retriever.invoke(x["standalone_question"])) | RunnablePassthrough.assign(context=lambda x: RunnableLambda(format_docs_and_log).invoke(x['context'])) | answer_prompt | llm | StrOutputParser())
                    return conversational_rag_chain.invoke({"question": question, "chat_history": get_buffer_string(chat_history_list[-settings.CHAT_HISTORY_WINDOW_SIZE_RAG:]), "user_provided_name": user_name_from_cache})
                final_bot_response = await asyncio.to_thread(run_rag_chain_sync)

            elif target_context.main_type == ContextMainType.DATABASE_QUERY:
                log_entry_data["intent"] = "TEXT_TO_SQL"

                chat_history_str = "\n".join([f"{msg.type}: {msg.content}" for msg in chat_history_list])
                sql_chain_result = await run_text_to_sql_lcel_chain(question=question, chat_history_str=chat_history_str, db_conn_config_for_sql=target_context.db_connection_config, llm=llm, sql_policy=target_context.processing_config or {})
                final_bot_response = sql_chain_result.get("final_answer_llm", "No se pudo generar una respuesta desde la BD.")
                log_entry_data["metadata_details_json"].update({"generated_sql": sql_chain_result.get("generated_sql")})
            
        log_entry_data["bot_response"] = final_bot_response

        if not has_history and final_bot_response and log_entry_data.get("intent") not in ["GREETING_STAGE", "AUTH_REQUIRED_PROMPT"]:
            response_to_cache = {"bot_response": final_bot_response, "metadata_details_json": log_entry_data.get("metadata_details_json", {})}
            cache_service.set_cached_response(api_client_id=current_api_client.id, context_ids=allowed_context_ids, question=question, response_dict=response_to_cache)
    
    ### CAMBIO 4: Manejo de Excepciones mejorado y más robusto ###
    except StopIteration as e:
        # Captura el flujo de "cache hit" y "auth required". El mensaje ya está en final_bot_response.
        print(f"[INFO] Flujo de chat terminado anticipadamente: {e}")
        # La respuesta ya se estableció antes de lanzar la excepción, por lo que el `finally` funcionará.
    
    except HTTPException as e:
        # Si nosotros lanzamos un HTTPException, queremos que el cliente reciba ese error específico.
        # Lo registramos en el log pero lo volvemos a lanzar.
        log_entry_data["error_message"] = f"HTTP Error: {e.status_code} - {e.detail}"
        log_entry_data["bot_response"] = e.detail
        await create_interaction_log(db_crud, log_entry_data)
        raise e # FastAPI lo convertirá en la respuesta HTTP correcta.

    except Exception as e:
        # Cualquier otra excepción es un error interno del servidor.
        print(f"CHAT_EP_CRITICAL_ERROR: {type(e).__name__} - {e}")
        traceback.print_exc()
        handoff_result = await _handle_human_handoff(user_log_identifier, question)
        log_entry_data["error_message"] = f"Internal Error: {type(e).__name__}"
        log_entry_data["bot_response"] = handoff_result["response_text"]

    
# ... (todo tu código hasta el inicio del bloque finally) ...

    finally:
        log_entry_data["response_time_ms"] = int((time.time() - start_time) * 1000)
        
        # ### CORRECCIÓN 1: Evitar AttributeError si 'error_message' es None ###
        # Condición para decidir si registrar en el historial de chat y en la DB de logs:
        # 1. Si NO hay "error_message" definido en log_entry_data
        # O 2. Si "error_message" es un string PERO NO comienza con "HTTP Error" (significa que no fue una HTTPException relanzada)
        should_log_history_and_db = True
        if "error_message" in log_entry_data:
            err_msg = log_entry_data["error_message"]
            if isinstance(err_msg, str) and err_msg.startswith("HTTP Error"):
                should_log_history_and_db = False # Fue un HTTP Exception que ya se relanzó y se maneja por FastAPI
            # Si err_msg es None, 'isinstance(err_msg, str)' es False, should_log_history_and_db se mantiene True. Esto lo maneja el segundo 'if'.

        if should_log_history_and_db:
            final_response_for_history = log_entry_data.get("bot_response", "")
            # Solo añade a la historia si hubo una respuesta y NO hubo un error de procesamiento general.
            if final_response_for_history and log_entry_data.get("error_message") is None: # Si no es None, significa que fue exitoso o StopIteration
                await asyncio.to_thread(history_manager.add_messages,
                    [HumanMessage(content=question), AIMessage(content=final_response_for_history)])
            
            # Siempre registramos en la DB de logs, a menos que sea un HTTP_EXCEPTION explícito
            # La distinción se hizo arriba con should_log_history_and_db
            await create_interaction_log(db_crud, log_entry_data)

    return ChatResponse(
        session_id=session_id, original_message=question,
        bot_response=log_entry_data.get("bot_response", "").strip(),
        metadata_details_json=log_entry_data.get("metadata_details_json", {})
    )