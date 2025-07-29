# app/api/endpoints/chat_api_endpoints.py

import time
import traceback
import asyncio
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Langchain Imports
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.documents import Document as LangchainCoreDocument
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain.chains import ConversationalRetrievalChain, LLMChain
from langchain.chains.question_answering import load_qa_chain
# ### [CORRECCIÓN] ### Usamos la memoria más simple para el objeto temporal
from langchain.memory import ConversationBufferMemory

# Módulos de la Aplicación
from app.db.session import get_crud_db_session
from app.models.api_client import ApiClient as ApiClientModel
from app.models.context_definition import ContextDefinition, ContextMainType
from app.schemas.schemas import ChatRequest, ChatResponse
from app.crud import create_interaction_log, crud_llm_model_config, crud_virtual_agent_profile
from app.config import settings
from app.security.api_key_auth import get_validated_api_client
from app.core.app_state import get_sync_vector_store, get_cached_llm_adapter
from ._chat_history_logic import FullyCustomChatMessageHistory
from app.services import cache_service
from app.tools.sql_tools import run_text_to_sql_lcel_chain

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

async def _handle_human_handoff(user_dni: str, question: str) -> str:
    ticket_id = f"TICKET-{int(time.time())}"
    return f"He creado un ticket de soporte ({ticket_id}). Un agente se pondrá en contacto contigo."

@router.post("/", response_model=ChatResponse)
async def process_chat_message(
    chat_request: ChatRequest,
    db_crud: AsyncSession = Depends(get_crud_db_session),
    current_api_client: ApiClientModel = Depends(get_validated_api_client)
):
    start_time = time.time()
    question = chat_request.message
    user_dni = chat_request.dni
    
    log_entry_data: Dict[str, Any] = {
        "user_dni": user_dni, "api_client_name": current_api_client.name, "user_message": question,
        "llm_model_used": "N/A", "bot_response": "[Error de procesamiento]", "intent": "UNKNOWN",
        "metadata_details_json": {}, "error_message": None, "retrieved_context_summary": None,
    }
    
    # Este es nuestro gestor REAL de la base de datos.
    db_history_manager = FullyCustomChatMessageHistory(session_id=user_dni)

    try:
        # Lógica de configuración... (se mantiene igual)
        api_client_settings = current_api_client.settings or {}
        allowed_context_ids = api_client_settings.get("allowed_context_ids", [])
        if not allowed_context_ids: raise HTTPException(status_code=403, detail="API Key sin contextos.")
        
        active_contexts_raw = (await db_crud.execute(select(ContextDefinition).where(ContextDefinition.id.in_(allowed_context_ids), ContextDefinition.is_active == True))).scalars().all()
        if not active_contexts_raw: raise HTTPException(status_code=404, detail="No hay contextos activos.")

        is_sql_intent = any(kw.lower() in question.lower() for kw in settings.SQL_INTENT_KEYWORDS)
        target_context = next((c for c in active_contexts_raw if c.main_type == ContextMainType.DATABASE_QUERY and is_sql_intent),
                              next((c for c in active_contexts_raw if c.main_type == ContextMainType.DOCUMENTAL), active_contexts_raw[0]))

        # Cargamos el historial REAL de la BD para la lógica
        chat_history_list = await asyncio.to_thread(lambda: db_history_manager.messages)
        has_history = len(chat_history_list) > 0
        
        # Lógica de caché...
        if not has_history:
            cached_result = cache_service.get_cached_response(
                api_client_id=current_api_client.id, context_ids=allowed_context_ids, question=question)
            if cached_result:
                log_entry_data.update({"llm_model_used": "CACHE", "intent": "CACHE_HIT", **cached_result})
                raise StopIteration("Respuesta encontrada en caché")
        
        # ... Lógica de selección de VAP y LLM ...
        vap_id_override = api_client_settings.get("default_virtual_agent_profile_id_override")
        llm_id_override = api_client_settings.get("default_llm_model_config_id_override")
        final_vap_id = vap_id_override or target_context.virtual_agent_profile_id
        if not final_vap_id: raise ValueError("No se pudo determinar un Perfil de Agente.")
        agent_profile = await crud_virtual_agent_profile.get_virtual_agent_profile_by_id(db_crud, final_vap_id)
        if not agent_profile: raise ValueError(f"Perfil de Agente ID {final_vap_id} no encontrado.")
        final_llm_id = llm_id_override or agent_profile.llm_model_config_id or target_context.default_llm_model_config_id
        if not final_llm_id: raise ValueError("No se pudo determinar un Modelo LLM.")
        llm_config = await crud_llm_model_config.get_llm_model_config_by_id(db_crud, final_llm_id)
        if not llm_config: raise ValueError(f"Modelo LLM ID {final_llm_id} no encontrado.")
        llm = await get_cached_llm_adapter(db_crud, model_config=llm_config)
        log_entry_data["llm_model_used"] = llm_config.display_name
        
        final_bot_response = ""

        if target_context.main_type == ContextMainType.DOCUMENTAL:
            log_entry_data["intent"] = "RAG_DOCUMENTAL"
            
            vector_store = get_sync_vector_store()
            retriever = vector_store.as_retriever(search_kwargs={"k": 5}) # 'filter' se maneja por permisos
            docs_qa_template = agent_profile.system_prompt or settings.DEFAULT_RAG_DOCS_QA_TEMPLATE

            # ### [CORRECCIÓN] ### Creamos una memoria TEMPORAL, solo para esta ejecución.
            # No está conectada a la base de datos.
            temporal_memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True, output_key='answer')
            # Le cargamos manualmente el historial REAL.
            for msg in chat_history_list:
                if isinstance(msg, HumanMessage):
                    temporal_memory.chat_memory.add_user_message(msg.content)
                elif isinstance(msg, AIMessage):
                    temporal_memory.chat_memory.add_ai_message(msg.content)

            q_gen_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template(settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE))
            combine_docs_chain = load_qa_chain(llm=llm, chain_type="stuff", prompt=ChatPromptTemplate.from_template(docs_qa_template))
            
            conversational_rag_chain = ConversationalRetrievalChain(
                retriever=retriever, question_generator=q_gen_chain, combine_docs_chain=combine_docs_chain, 
                memory=temporal_memory, # Le pasamos la memoria TEMPORAL
                return_source_documents=True)
            
            rag_result = await asyncio.to_thread(conversational_rag_chain.invoke, {"question": question})
            final_bot_response = rag_result.get("answer", "")
            retrieved_docs: List[LangchainCoreDocument] = rag_result.get("source_documents", [])
            
            if retrieved_docs:
                unique_metadata = []
                seen_sources = set()
                for doc in retrieved_docs:
                    source_key = doc.metadata.get("source_filename")
                    if source_key and source_key not in seen_sources:
                        unique_metadata.append(doc.metadata)
                        seen_sources.add(source_key)
                log_entry_data["metadata_details_json"]["source_documents"] = unique_metadata
                log_entry_data["retrieved_context_summary"] = "\n".join([f"Doc: {meta.get('source_filename', 'N/A')}" for meta in unique_metadata[:3]]) + "..."

        elif target_context.main_type == ContextMainType.DATABASE_QUERY:
            log_entry_data["intent"] = "TEXT_TO_SQL"
            chat_history_str = "\n".join([f"{msg.type}: {msg.content}" for msg in chat_history_list])
            sql_chain_result = await run_text_to_sql_lcel_chain(
                question=question, chat_history_str=chat_history_str, db_conn_config_for_sql=target_context.db_connection_config, llm=llm,
                sql_policy=target_context.processing_config or {})
            final_bot_response = sql_chain_result.get("final_answer_llm", "No se pudo generar una respuesta desde la BD.")
            log_entry_data["metadata_details_json"].update({"generated_sql": sql_chain_result.get("generated_sql")})
        
        log_entry_data["bot_response"] = final_bot_response

        if not has_history and final_bot_response:
            response_to_cache = {"bot_response": final_bot_response, "metadata_details_json": log_entry_data.get("metadata_details_json", {})}
            cache_service.set_cached_response(
                api_client_id=current_api_client.id, context_ids=allowed_context_ids, 
                question=question, response_dict=response_to_cache)

    except StopIteration as e:
        print(f"[INFO] Flujo controlado terminado: {e}")
    except Exception as e:
        print(f"CHAT_EP_CRITICAL_ERROR: {type(e).__name__} - {e}")
        traceback.print_exc()
        log_entry_data.update({"error_message": f"Error Interno: {type(e).__name__}", "bot_response": await _handle_human_handoff(user_dni, question)})
    
    finally:
        log_entry_data["response_time_ms"] = int((time.time() - start_time) * 1000)
        final_bot_response_to_log = log_entry_data.get("bot_response", "")
        # ### [CORRECCIÓN] ### El finally ahora es el ÚNICO lugar que guarda en la base de datos
        if final_bot_response_to_log and not log_entry_data.get("error_message"):
            await asyncio.to_thread(
                db_history_manager.add_messages,
                [HumanMessage(content=question), AIMessage(content=final_bot_response_to_log)])
        
        await create_interaction_log(db_crud, log_entry_data)
        
    return ChatResponse(
        dni=user_dni, original_message=question,
        bot_response=log_entry_data.get("bot_response", "").strip(),
        metadata_details_json=log_entry_data.get("metadata_details_json", {})
    )