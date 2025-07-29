# app/api/endpoints/chat_api_endpoints.py

import time
import traceback
import asyncio
from typing import Dict, Any, List
import json # <--- AÑADE ESTA LÍNEA

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
from app.tools.sql_tools import run_db_query_chain

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

# Constantes para los estados de la conversación.
CONV_STATE_AWAITING_NAME = "awaiting_name_confirmation"
CONV_STATE_AWAITING_TOOL_PARAMS = "awaiting_tool_parameters" # <-- NUEVA


async def _handle_human_handoff(user_identifier: str, question: str) -> Dict[str, str]:
    ticket_id = f"TICKET-{int(time.time())}"
    response_text = f"He creado un ticket de soporte ({ticket_id}). Un agente se pondrá en contacto contigo para resolver tu consulta."
    return {"ticket_id": ticket_id, "response_text": response_text}


# app/api/endpoints/chat_api_endpoints.py

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
    
    # 1. INICIALIZACIÓN DE VARIABLES
    log_entry_data: Dict[str, Any] = { "user_dni": user_log_identifier, "api_client_name": current_api_client.name, "user_message": question, "bot_response": "[Error de procesamiento]", "intent": "UNKNOWN", "metadata_details_json": {}, "error_message": None, "retrieved_context_summary": None}
    history_manager = FullyCustomChatMessageHistory(session_id=session_id)
    final_bot_response = ""
    
    try:
        # 2. CARGA DE CONFIGURACIÓN Y CONTEXTOS
        api_client_settings = current_api_client.settings or {}
        allowed_context_ids = api_client_settings.get("allowed_context_ids", [])
        if not allowed_context_ids: raise HTTPException(403, "API Key sin contextos.")

        stmt_base = select(ContextDefinition).where(ContextDefinition.id.in_(allowed_context_ids), ContextDefinition.is_active == True).options(selectinload(ContextDefinition.db_connection_config))
        
        # 3. FILTRADO DE VISIBILIDAD DE CONTEXTOS Y LÓGICA DE LOGIN REQUERIDO
        if chat_request.is_authenticated_user:
            result = await db_crud.execute(stmt_base)
            active_contexts = result.scalars().unique().all()
        else:
            public_contexts_query = stmt_base.filter(ContextDefinition.is_public == True)
            result = await db_crud.execute(public_contexts_query)
            active_contexts = result.scalars().unique().all()
            
            db_intent_keywords = getattr(settings, 'DB_INTENT_KEYWORDS', ["nota", "horario", "mis "])
            is_potential_private_query = any(kw.lower() in question.lower() for kw in db_intent_keywords)
            if is_potential_private_query and not any(c.main_type == ContextMainType.DATABASE_QUERY for c in active_contexts):
                private_db_contexts_exist_query = stmt_base.filter(ContextDefinition.main_type == ContextMainType.DATABASE_QUERY, ContextDefinition.is_public == False)
                count_result = await db_crud.execute(select(func.count()).select_from(private_db_contexts_exist_query.subquery()))
                if count_result.scalar_one() > 0:
                    log_entry_data.update({"intent": "AUTH_REQUIRED_PROMPT", "bot_response": "Para esta consulta, necesito que inicies sesión.", "metadata_details_json": {"action_required": "request_login"}})
                    raise StopIteration("Usuario invitado requiere login.")

        if not active_contexts: raise HTTPException(404, "No hay contextos válidos para su nivel de acceso.")
        
        # 4. PREPARACIÓN (HISTORIAL, VAP, LLM)
        chat_history_list = await asyncio.to_thread(lambda: history_manager.messages)
        has_history = len(chat_history_list) > 0
        
        vap_id = api_client_settings.get("default_virtual_agent_profile_id_override") or active_contexts[0].virtual_agent_profile_id
        agent_profile = await crud_virtual_agent_profile.get_fully_loaded_profile(db_crud, vap_id)
        llm_config_id = api_client_settings.get("default_llm_model_config_id_override") or agent_profile.llm_model_config_id or active_contexts[0].default_llm_model_config_id
        llm_config = await crud_llm_model_config.get_llm_model_config_by_id(db_crud, llm_config_id)
        if not llm_config or not agent_profile: raise ValueError("No se pudo cargar la configuración de Agente o LLM.")

        llm = await get_cached_llm_adapter(db_crud, model_config=llm_config)
        log_entry_data["llm_model_used"] = llm_config.display_name
        
        # 5. MÁQUINA DE ESTADOS
        current_conv_state = cache_service.get_cache(f"chat_state:{session_id}")

        if not has_history and question == "__INICIAR_CHAT__": # ETAPA 1
            log_entry_data["intent"] = "GREETING_STAGE"
            chain = ChatPromptTemplate.from_template(agent_profile.greeting_prompt) | llm | StrOutputParser()
            final_bot_response = await chain.ainvoke({"user_name": chat_request.user_name or "Usuario"})
            if agent_profile.name_confirmation_prompt: cache_service.set_cache(f"chat_state:{session_id}", CONV_STATE_AWAITING_NAME, ttl_seconds=300)

        elif current_conv_state == CONV_STATE_AWAITING_NAME: # ETAPA 2
            log_entry_data["intent"] = "NAME_CAPTURE_STAGE"
            user_provided_name = question.strip()
            cache_service.set_cache(f"user_name:{session_id}", user_provided_name, ttl_seconds=settings.CACHE_EXPIRATION_SECONDS)
            chain = ChatPromptTemplate.from_template(agent_profile.name_confirmation_prompt) | llm | StrOutputParser()
            final_bot_response = await chain.ainvoke({"user_provided_name": user_provided_name})
            cache_service.delete_cache(f"chat_state:{session_id}")
        
        # ETAPA 2.5: BUCLE DE RECOLECCIÓN DE PARÁMETROS
        elif current_conv_state == CONV_STATE_AWAITING_TOOL_PARAMS:
            log_entry_data["intent"] = "TOOL_PARAM_FILL"
            
            state_data = cache_service.get_cache(f"tool_state:{session_id}")
            if not state_data:
                # Si el estado se pierde por alguna razón, salimos del bucle
                cache_service.delete_cache(f"chat_state:{session_id}")
                # Forzamos una re-evaluación en la ETAPA 3
                return await process_chat_message(chat_request, db_crud, current_api_client)

            context_id = state_data["context_id"]
            stmt = select(ContextDefinition).where(ContextDefinition.id == context_id).options(selectinload(ContextDefinition.db_connection_config))
            target_context = (await db_crud.execute(stmt)).scalar_one_or_none()
            if not target_context or not target_context.db_connection_config:
                raise ValueError(f"No se pudo recargar el contexto de BD válido ID {context_id}")

            db_query_result = await run_db_query_chain(
                question=question, # Usamos la nueva pregunta del usuario para la extracción
                chat_history_str=get_buffer_string(chat_history_list),
                db_conn_config=target_context.db_connection_config,
                processing_config=target_context.processing_config or {},
                llm=llm,
                user_dni=chat_request.user_dni,
                current_params=state_data.get("partial_parameters", {}) # Pasamos los params que ya teníamos
            )
            
            intent = db_query_result.get("intent")
            final_bot_response = db_query_result.get("final_answer")
            
            if intent == "CLARIFICATION_REQUIRED":
                # Aún faltan datos, así que actualizamos el estado en Redis
                print("CHAT_API: Aún faltan parámetros. Actualizando estado en Redis.")
                new_state = {**state_data, **db_query_result.get("metadata", {})}
                cache_service.set_cache(f"tool_state:{session_id}", new_state, ttl_seconds=300)
            else:
                # ¡Conseguido! Limpiamos todo.
                print("CHAT_API: Tarea completada o fallida. Limpiando estado.")
                cache_service.delete_cache(f"chat_state:{session_id}")
                cache_service.delete_cache(f"tool_state:{session_id}")
            
            log_entry_data.update({"intent": intent, "metadata_details_json": db_query_result.get("metadata", {})})

        else:
            # Separamos los contextos disponibles
            db_contexts = [c for c in active_contexts if c.main_type == ContextMainType.DATABASE_QUERY]
            doc_contexts = [c for c in active_contexts if c.main_type == ContextMainType.DOCUMENTAL]
            target_context = None

            # Estrategia de Selección de Contexto
            db_intent_keywords = getattr(settings, 'DB_INTENT_KEYWORDS', 
                ["nota", "horario", "promedio", "calificaciones", "consultar", "cuántos", "lista", "mis "])
            is_explicit_db_intent = any(kw.lower() in question.lower() for kw in db_intent_keywords)
            
            if is_explicit_db_intent and db_contexts:
                target_context = db_contexts[0]
            elif doc_contexts:
                target_context = doc_contexts[0]
            elif active_contexts:
                target_context = active_contexts[0]
            else:
                # Este caso ya está cubierto antes, pero es una buena salvaguarda
                raise HTTPException(status_code=404, detail="No se encontró ningún contexto aplicable.")
            
            print(f"SELECTOR: Contexto seleccionado: '{target_context.name}' (Tipo: {target_context.main_type.value})")
            
            # --- Ejecutamos la cadena correspondiente al contexto seleccionado ---
            
            if target_context.main_type == ContextMainType.DOCUMENTAL:
                log_entry_data["intent"] = "RAG_DOCUMENTAL"
                user_name_from_cache = cache_service.get_cache(f"user_name:{session_id}") or chat_request.user_name or "Usuario"
                
                def run_rag_chain_sync():
                    condense_question_prompt = PromptTemplate.from_template(settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE)
                    answer_prompt = ChatPromptTemplate.from_template(agent_profile.system_prompt)
                    standalone_question_chain = condense_question_prompt | llm | StrOutputParser()
                    vector_store = get_sync_vector_store()
                    context_names_for_filter = [ctx.name for ctx in doc_contexts]
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

                    conversational_rag_chain = (
                        RunnablePassthrough.assign(
                            standalone_question=RunnablePassthrough.assign(
                                chat_history=lambda x: get_buffer_string(chat_history_list)
                            ) | standalone_question_chain
                        )
                        | RunnablePassthrough.assign(context=lambda x: retriever.invoke(x["standalone_question"]))
                        | RunnablePassthrough.assign(context=lambda x: RunnableLambda(format_docs_and_log).invoke(x['context']))
                        | answer_prompt | llm | StrOutputParser()
                    )
                    return conversational_rag_chain.invoke({
                        "question": question, 
                        "chat_history": get_buffer_string(chat_history_list),
                        "user_provided_name": user_name_from_cache
                    })
                
                final_bot_response = await asyncio.to_thread(run_rag_chain_sync)


            elif target_context.main_type == ContextMainType.DATABASE_QUERY:
                db_query_result = await run_db_query_chain(
                    question=question,
                    chat_history_str=get_buffer_string(chat_history_list),
                    db_conn_config=target_context.db_connection_config,
                    processing_config=target_context.processing_config or {},
                    llm=llm,
                    user_dni=chat_request.user_dni
                )
                
                intent = db_query_result.get("intent")
                final_bot_response = db_query_result.get("final_answer")
                log_entry_data.update({"intent": intent, "metadata_details_json": db_query_result.get("metadata", {})})

                if intent == "CLARIFICATION_REQUIRED":
                    print("CHAT_API: La herramienta requiere clarificación. Guardando estado para iniciar el bucle.")
                    metadata = db_query_result.get("metadata", {})
                    tool_config = next((t for t in (target_context.processing_config or {}).get("tools", [])), None)
                    if tool_config:
                        state_to_save = {
                            "original_question": question, 
                            "context_id": target_context.id,
                            "tool_config": tool_config, 
                            **metadata
                        }
                        cache_service.set_cache(f"chat_state:{session_id}", CONV_STATE_AWAITING_TOOL_PARAMS, ttl_seconds=300)
                        cache_service.set_cache(f"tool_state:{session_id}", state_to_save, ttl_seconds=300)
        
        # --- ASIGNACIÓN FINAL Y LÓGICA DE CACHÉ ---
        log_entry_data["bot_response"] = final_bot_response

        if not has_history and final_bot_response and log_entry_data.get("intent") not in ["GREETING_STAGE", "NAME_CAPTURE_STAGE", "AUTH_REQUIRED_PROMPT", "CLARIFICATION_REQUIRED"]:
            response_to_cache = {"bot_response": final_bot_response, "metadata_details_json": log_entry_data.get("metadata_details_json", {})}
            cache_service.set_cached_response(api_client_id=current_api_client.id, context_ids=[c.id for c in active_contexts], question=question, response_dict=response_to_cache)

    # --- MANEJO DE EXCEPCIONES Y FINALIZACIÓN ---
    except StopIteration:
        print(f"[INFO] Flujo terminado anticipadamente (ej. AUTH_REQUIRED). La respuesta ya está en log_entry_data.")
        # La respuesta ya está establecida, no hacemos nada más.
    except HTTPException as e:
        log_entry_data.update({"error_message": f"HTTP Error: {e.detail}", "bot_response": e.detail})
        # Registramos el log y relanzamos para que FastAPI envíe el error 4xx/5xx correcto
        await create_interaction_log(db_crud, log_entry_data)
        raise e
    except Exception as e:
        print(f"CHAT_EP_CRITICAL_ERROR: {type(e).__name__} - {e}"); traceback.print_exc()
        handoff = await _handle_human_handoff(user_log_identifier, question)
        log_entry_data.update({"error_message": f"Internal Error: {type(e).__name__}", "bot_response": handoff["response_text"]})
    finally:
        log_entry_data["response_time_ms"] = int((time.time() - start_time) * 1000)
        try:
            # Sanitizar metadatos antes de guardar
            metadata_to_log = log_entry_data.get("metadata_details_json", {})
            log_entry_data["metadata_details_json"] = json.loads(json.dumps(metadata_to_log, default=str))
        except Exception:
            log_entry_data["metadata_details_json"] = {"serialization_error": "Could not serialize metadata"}
        
        # Guardar en la DB a menos que fuera un HTTPException ya manejado
        if not (log_entry_data.get("error_message") and "HTTP Error" in log_entry_data["error_message"]):
            await create_interaction_log(db_crud, log_entry_data)
        
        # Añadir al historial de chat en Redis si la interacción fue exitosa
        if log_entry_data.get("bot_response") and not log_entry_data.get("error_message"):
            await asyncio.to_thread(history_manager.add_messages,
                [HumanMessage(content=question), AIMessage(content=log_entry_data["bot_response"])])
        
    

    return ChatResponse(
        session_id=session_id, original_message=question,
        bot_response=log_entry_data.get("bot_response", "").strip(),
        metadata_details_json=log_entry_data.get("metadata_details_json", {})
    )