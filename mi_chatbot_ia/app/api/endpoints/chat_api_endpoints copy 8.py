# app/api/endpoints/chat_api_endpoints_old.py

# ==========================================================
# ===   CÓDIGO COMPLETO FINAL - BASADO EN TU VERSIÓN ORIGINAL  ===
# ==========================================================
import time
import traceback
import asyncio
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.documents import Document as LangchainCoreDocument
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain.chains import ConversationalRetrievalChain, RetrievalQA, LLMChain
from langchain.chains.question_answering import load_qa_chain
from langchain.memory import ConversationBufferWindowMemory

from app.db.session import get_crud_db_session
from app.models.api_client import ApiClient as ApiClientModel
from app.models.context_definition import ContextDefinition
from app.schemas.schemas import ChatRequest, ChatResponse
from app.crud import create_interaction_log, crud_llm_model_config, crud_virtual_agent_profile, get_contexts_for_user_dni
from app.config import settings
from app.security.api_key_auth import get_validated_api_client
from app.core.app_state import get_sync_vector_store, get_cached_llm_adapter
from ._chat_history_logic import FullyCustomChatMessageHistory, ContextAwareFilteredHistory
from app.services import cache_service

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

# ==========================================================
# ===   FUNCIÓN AUXILIAR SÍNCRONA: LA "CAJA NEGRA"       ===
# ==========================================================
def _run_rag_pipeline_sync(
    question: str, 
    llm, 
    retriever, 
    chat_history_list: List, 
    unfiltered_history: FullyCustomChatMessageHistory, 
    resolved_context_names: List[str], 
    virtual_agent_profile
) -> Dict[str, Any]:
    """Toda la lógica de LangChain se ejecuta aquí en modo síncrono."""
    has_history = len(chat_history_list) > 0
    docs_qa_template = virtual_agent_profile.system_prompt if virtual_agent_profile else settings.DEFAULT_RAG_DOCS_QA_TEMPLATE

    # Replicamos TU lógica original FUNCIONAL
    if not has_history:
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm, chain_type="stuff", retriever=retriever,
            chain_type_kwargs={"prompt": ChatPromptTemplate.from_template(docs_qa_template)}, return_source_documents=True)
        rag_result = qa_chain.invoke({"query": question})
        return {"bot_response": rag_result.get("result", ""), "source_documents": rag_result.get("source_documents", [])}
    else:
        context_aware_history = ContextAwareFilteredHistory(unfiltered_history, resolved_context_names)
        rag_memory = ConversationBufferWindowMemory(memory_key="chat_history", chat_memory=context_aware_history, return_messages=True, output_key='answer')
        q_gen_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template(settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE))
        combine_docs_chain = load_qa_chain(llm=llm, chain_type="stuff", prompt=ChatPromptTemplate.from_template(docs_qa_template))
        conversational_rag_chain = ConversationalRetrievalChain(
            retriever=retriever, question_generator=q_gen_chain, combine_docs_chain=combine_docs_chain, 
            memory=rag_memory, return_source_documents=True)
        rag_result = conversational_rag_chain.invoke({"question": question})
        return {"bot_response": rag_result.get("answer", ""), "source_documents": rag_result.get("source_documents", [])}
    
async def _handle_human_handoff(user_dni: str, question: str) -> str:
    ticket_id = f"TICKET-{int(time.time())}"
    print(f"HANDOFF: Derivando a humano. DNI: {user_dni}, Ticket: {ticket_id}")
    return f"En este momento no puedo resolver tu consulta. He creado un ticket ({ticket_id}) y un agente se pondrá en contacto contigo."


@router.post("/", response_model=ChatResponse)
async def process_chat_message_langchain(
    chat_request: ChatRequest,
    db_crud: AsyncSession = Depends(get_crud_db_session),
    current_api_client: ApiClientModel = Depends(get_validated_api_client)
):
    start_time = time.time()
    question = chat_request.message
    user_dni_session_id = chat_request.dni
    api_client_settings = current_api_client.settings or {}
    
    log_entry_data: Dict[str, Any] = {
        "user_dni": user_dni_session_id, "api_client_name": current_api_client.name, "user_message": question,
        "llm_model_used": "N/A", "bot_response": "[Error de procesamiento]", "intent": "UNKNOWN",
        "metadata_details_json": {}, "error_message": None, "retrieved_context_summary": None,
    }

    try:
        # === PASO 1: Lógica de Permisos ===
        client_contexts_ids = set(api_client_settings.get("allowed_context_ids", []))
        user_role_contexts_ids = set(await get_contexts_for_user_dni(db_crud, user_dni_session_id))
        final_allowed_context_ids = list(client_contexts_ids | user_role_contexts_ids)
        if not final_allowed_context_ids: raise HTTPException(status_code=400, detail="Acceso denegado.")
        
        stmt_names = select(ContextDefinition.name).where(ContextDefinition.id.in_(final_allowed_context_ids), ContextDefinition.is_active == True)
        resolved_context_names = (await db_crud.execute(stmt_names)).scalars().all()
        if not resolved_context_names: raise HTTPException(status_code=404, detail="No se encontraron contextos activos.")

        # === PASO 2: Lógica de Caché ===
        unfiltered_history = FullyCustomChatMessageHistory(session_id=user_dni_session_id)
        chat_history_list = await asyncio.to_thread(lambda: unfiltered_history.messages)
        has_history = len(chat_history_list) > 0
        if not has_history:
            cached_result = cache_service.get_cached_response(
                api_client_id=current_api_client.id, context_ids=final_allowed_context_ids, question=question)
            if cached_result:
                log_entry_data.update({"llm_model_used": "CACHE", "intent": "CACHE_HIT", **cached_result})
                raise StopIteration("Respuesta encontrada en caché")

        # --- PASO 3: SETUP con el Vector Store SÍNCRONO ---
        llm_model_config_id = api_client_settings.get("default_llm_model_config_id_override")
        if not llm_model_config_id: raise HTTPException(status_code=400, detail="Cliente API no tiene un modelo LLM configurado.")
        
        llm = await get_cached_llm_adapter(db_crud, llm_model_config_id)
        llm_config = await crud_llm_model_config.get_llm_model_config_by_id(db_crud, llm_model_config_id)
        if llm_config: log_entry_data["llm_model_used"] = llm_config.display_name

        vap_id = api_client_settings.get("default_virtual_agent_profile_id_override")
        virtual_agent_profile = await crud_virtual_agent_profile.get_virtual_agent_profile_by_id(db_crud, vap_id) if vap_id else None
        
        # <<< --- ¡AQUÍ ESTÁ LA ÚNICA LÍNEA QUE CAMBIA RESPECTO A TU CÓDIGO ORIGINAL! --- >>>
        vector_store = get_sync_vector_store()  
        
        retriever = vector_store.as_retriever(search_kwargs={"k": 15, "filter": {"context_name": {"$in": resolved_context_names}}})
        docs_qa_template = virtual_agent_profile.system_prompt if virtual_agent_profile else settings.DEFAULT_RAG_DOCS_QA_TEMPLATE

        # --- PASO 4: EJECUCIÓN AISLADA (Tu lógica original en un thread) ---
        rag_result: Dict[str, Any] = {}
        if not has_history:
            qa_chain = RetrievalQA.from_chain_type(
                llm=llm, chain_type="stuff", retriever=retriever,
                chain_type_kwargs={"prompt": ChatPromptTemplate.from_template(docs_qa_template)}, return_source_documents=True)
            rag_result = await asyncio.to_thread(qa_chain.invoke, {"query": question})
            log_entry_data["bot_response"] = rag_result.get("result", "")
        else:
            context_aware_history = ContextAwareFilteredHistory(unfiltered_history, resolved_context_names)
            rag_memory = ConversationBufferWindowMemory(memory_key="chat_history", chat_memory=context_aware_history, return_messages=True, output_key='answer')
            q_gen_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template(settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE))
            combine_docs_chain = load_qa_chain(llm=llm, chain_type="stuff", prompt=ChatPromptTemplate.from_template(docs_qa_template))
            conversational_rag_chain = ConversationalRetrievalChain(
                retriever=retriever, question_generator=q_gen_chain, combine_docs_chain=combine_docs_chain, 
                memory=rag_memory, return_source_documents=True)
            rag_result = await asyncio.to_thread(conversational_rag_chain.invoke, {"question": question})
            log_entry_data["bot_response"] = rag_result.get("answer", "")
        
        retrieved_docs: List[LangchainCoreDocument] = rag_result.get("source_documents", [])
        if retrieved_docs: 
            log_entry_data["retrieved_context_summary"] = "\n".join([f"Doc: {doc.metadata.get('source_filename', 'N/A')}" for doc in retrieved_docs[:3]]) + "..."

        if not log_entry_data["bot_response"] and not retrieved_docs:
            base_response = "No he encontrado información específica sobre tu pregunta."
            if resolved_context_names: base_response += f" Sin embargo, puedo ayudarte con temas como: {', '.join(resolved_context_names)}."
            log_entry_data["bot_response"] = base_response

        # --- PASO 5: Guardar en Caché ---
        if not has_history and log_entry_data["bot_response"]:
            response_to_cache = {"bot_response": log_entry_data["bot_response"], "metadata_details_json": log_entry_data.get("metadata_details_json", {})}
            cache_service.set_cached_response(api_client_id=current_api_client.id, context_ids=final_allowed_context_ids, question=question, response_dict=response_to_cache)

    except StopIteration as e:
        print(f"[INFO] Flujo controlado terminado: {e}")
    except Exception as e:
        print(f"CHAT_EP_CRITICAL_ERROR: {type(e).__name__} - {e}")
        traceback.print_exc()
        log_entry_data.update({"error_message": f"Error Interno: {type(e).__name__}", "bot_response": await _handle_human_handoff(user_dni_session_id, question)})
    
    finally:
        log_entry_data["response_time_ms"] = int((time.time() - start_time) * 1000)
        final_bot_response = log_entry_data.get("bot_response", "")
        if final_bot_response and not log_entry_data.get("error_message"):
            await asyncio.to_thread(unfiltered_history.add_messages, [HumanMessage(content=question), AIMessage(content=final_bot_response)])
        await create_interaction_log(db_crud, log_entry_data)
        
    return ChatResponse(
        dni=user_dni_session_id, original_message=question,
        bot_response=log_entry_data.get("bot_response", "").strip(),
        metadata_details_json=log_entry_data.get("metadata_details_json", {})
    )