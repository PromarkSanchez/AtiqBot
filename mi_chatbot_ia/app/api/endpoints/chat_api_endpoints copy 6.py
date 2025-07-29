# app/api/endpoints/chat_api_endpoints.py
import time
import traceback
import asyncio
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

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
from app.crud import crud_interaction_log, crud_context_definition, crud_llm_model_config, crud_virtual_agent_profile
from app.config import settings
from app.security.api_key_auth import get_validated_api_client
from app.core.app_state import get_vector_store, get_cached_llm_adapter
from ._chat_history_logic import FullyCustomChatMessageHistory, ContextAwareFilteredHistory, select_human_agent_for_handoff, create_ticket_for_handoff

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

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
    
    # [SOLUCIÓN] Definimos el diccionario log_entry_data al principio con valores iniciales
    log_entry_data: Dict[str, Any] = {
        "user_dni": user_dni_session_id,
        "api_client_name": current_api_client.name,
        "user_message": question,
        "llm_model_used": "N/A", # Placeholder
        "bot_response": "[Error de procesamiento]",
        "intent": "UNKNOWN",
        "metadata_details_json": {},
        "error_message": None,
        "retrieved_context_summary": None,
    }

    try:
        # 1. --- OBTENCIÓN DE CONFIGURACIONES (LLM y Agente) ---
        llm_model_config_id = api_client_settings.get("default_llm_model_config_id_override")
        if not llm_model_config_id:
            raise HTTPException(status_code=400, detail="Cliente API no tiene un modelo LLM configurado.")
        
        llm = await get_cached_llm_adapter(db_crud, llm_model_config_id)
        llm_model_config = await crud_llm_model_config.get_llm_model_config_by_id(db_crud, llm_model_config_id)
        if llm_model_config:
            log_entry_data["llm_model_used"] = llm_model_config.display_name # Actualizamos el log

        vap_id = api_client_settings.get("default_virtual_agent_profile_id_override")
        virtual_agent_profile = await crud_virtual_agent_profile.get_virtual_agent_profile_by_id(db_crud, vap_id) if vap_id else None

        # 2. --- PREPARACIÓN DE CONTEXTO Y HISTORIAL ---
        allowed_context_ids = api_client_settings.get("allowed_context_ids", [])
        stmt = select(ContextDefinition.name).where(ContextDefinition.id.in_(allowed_context_ids), ContextDefinition.is_active == True)
        resolved_context_names = (await db_crud.execute(stmt)).scalars().all()
        
        unfiltered_history = FullyCustomChatMessageHistory(session_id=user_dni_session_id)
        chat_history_list = await asyncio.to_thread(lambda: unfiltered_history.messages)
        has_history = len(chat_history_list) > 0
        
        vector_store = get_vector_store()
        retriever = vector_store.as_retriever(search_kwargs={"k": 15, "filter": {"context_name": {"$in": resolved_context_names}}})
        
        docs_qa_template = virtual_agent_profile.system_prompt if virtual_agent_profile and virtual_agent_profile.system_prompt else settings.DEFAULT_RAG_DOCS_QA_TEMPLATE

        # 3. --- EJECUCIÓN DEL RAG ---
        rag_result: Dict[str, Any] = {}
        if not has_history:
            # RUTA RÁPIDA ...
            qa_chain = RetrievalQA.from_chain_type(
                llm=llm, chain_type="stuff", retriever=retriever,
                chain_type_kwargs={"prompt": ChatPromptTemplate.from_template(docs_qa_template)},
                return_source_documents=True,
            )
            rag_result = await asyncio.to_thread(qa_chain.invoke, {"query": question})
            log_entry_data["bot_response"] = rag_result.get("result", "")
        else:
            # RUTA COMPLETA ...
            context_aware_history = ContextAwareFilteredHistory(unfiltered_history, resolved_context_names)
            rag_memory = ConversationBufferWindowMemory(memory_key="chat_history", chat_memory=context_aware_history, return_messages=True, output_key='answer')
            q_gen_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template(settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE))
            combine_docs_chain = load_qa_chain(llm=llm, chain_type="stuff", prompt=ChatPromptTemplate.from_template(docs_qa_template))
            conversational_rag_chain = ConversationalRetrievalChain(retriever=retriever, question_generator=q_gen_chain, combine_docs_chain=combine_docs_chain, memory=rag_memory, return_source_documents=True)
            rag_result = await asyncio.to_thread(conversational_rag_chain.invoke, {"question": question})
            log_entry_data["bot_response"] = rag_result.get("answer", "")
        
        retrieved_docs: List[LangchainCoreDocument] = rag_result.get("source_documents", [])
        if retrieved_docs:
            log_entry_data["retrieved_context_summary"] = "\n".join([f"Doc: {doc.metadata.get('source_filename', 'N/A')}" for doc in retrieved_docs[:3]]) + "..."

    except Exception as e:
        print(f"CHAT_EP_CRITICAL_ERROR: {type(e).__name__} - {e}")
        traceback.print_exc()
        log_entry_data["error_message"] = f"Error Interno: {type(e).__name__}"
    
    finally:
        log_entry_data["response_time_ms"] = int((time.time() - start_time) * 1000)
        
        if not log_entry_data.get("error_message"):
            await asyncio.to_thread(
                unfiltered_history.add_messages,
                [HumanMessage(content=question), AIMessage(content=log_entry_data["bot_response"])]
            )
        
        await crud_interaction_log.create_interaction_log(db_crud, log_entry_data)
        
    return ChatResponse(
        dni=user_dni_session_id,
        original_message=question,
        bot_response=log_entry_data.get("bot_response", "").strip(),
        metadata_details_json=log_entry_data.get("metadata_details_json", {})
    )