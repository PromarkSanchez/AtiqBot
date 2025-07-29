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
from sqlalchemy.orm import selectinload


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
    
    log_entry_data: Dict[str, Any] = {
        "user_dni": user_dni_session_id, "api_client_name": current_api_client.name, "user_message": question,
        "llm_model_used": "N/A", "bot_response": "[Error de procesamiento]", "intent": "RAG",
        "metadata_details_json": {}, "error_message": None, "retrieved_context_summary": None,
    }

    try:
        # 1. Obtener Configuraciones
        llm_model_config_id = api_client_settings.get("default_llm_model_config_id_override")
        if not llm_model_config_id: raise HTTPException(status_code=400, detail="Cliente API sin modelo LLM configurado.")
        
        llm = await get_cached_llm_adapter(db_crud, llm_model_config_id)
        llm_config = await crud_llm_model_config.get_llm_model_config_by_id(db_crud, llm_model_config_id)
        if llm_config: log_entry_data["llm_model_used"] = llm_config.display_name
        
        vap_id = api_client_settings.get("default_virtual_agent_profile_id_override")
        virtual_agent_profile = await crud_virtual_agent_profile.get_virtual_agent_profile_by_id(db_crud, vap_id) if vap_id else None

        # 2. Preparar Filtros y Prompts
        allowed_context_ids = api_client_settings.get("allowed_context_ids", [])
        stmt_contexts = select(ContextDefinition).options(selectinload(ContextDefinition.document_sources)).where(ContextDefinition.id.in_(allowed_context_ids), ContextDefinition.is_active == True)
        active_contexts = (await db_crud.execute(stmt_contexts)).scalars().unique().all()
        if not active_contexts: raise ValueError("Cliente API sin acceso a contextos activos.")
        
        active_source_ids = [source.id for context in active_contexts for source in context.document_sources if source.is_active]
        if not active_source_ids: raise ValueError("No se encontraron fuentes de documentos activas.")
        
        rag_metadata_filter = {"source_doc_source_id": {"$in": active_source_ids}}
        qa_prompt_template = virtual_agent_profile.system_prompt if virtual_agent_profile and virtual_agent_profile.system_prompt else settings.DEFAULT_RAG_DOCS_QA_TEMPLATE

        # 3. Preparar historial
        unfiltered_history = FullyCustomChatMessageHistory(session_id=user_dni_session_id)
        chat_history_list = await asyncio.to_thread(lambda: unfiltered_history.messages)
        has_history = len(chat_history_list) > 0
        
        # 4. Determinar la pregunta a usar para la búsqueda
        question_for_retrieval = question
        if has_history:
            print("PERF_DEBUG: Con historial, generando pregunta independiente...")
            q_gen_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template(settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE))
            question_for_retrieval = await q_gen_chain.ainvoke({"chat_history": chat_history_list, "question": question})
            question_for_retrieval = question_for_retrieval.get("text", question)

        # 5. [JAULA DE ACERO] Ejecutar el retrieval ANTES de llamar a la cadena de respuesta
        print(f"RETRIEVAL: Buscando documentos para la pregunta: '{question_for_retrieval}'")
        vector_store = get_vector_store()
        retriever = vector_store.as_retriever(search_kwargs={"k": 15, "filter": rag_metadata_filter})
        retrieved_docs: List[LangchainCoreDocument] = await asyncio.to_thread(retriever.get_relevant_documents, question_for_retrieval)

        if not retrieved_docs:
            # Si no hay documentos, construimos la respuesta con sugerencias SIN llamar al LLM
            print("VALIDATION: No se recuperaron documentos. Forzando respuesta con sugerencias.")
            base_response = "No he encontrado información específica sobre tu pregunta."
            topics = [context.name for context in active_contexts]
            if topics:
                topics_str = ", ".join(topics)
                sugg_response = f" Sin embargo, puedo ayudarte con los siguientes temas: {topics_str}. ¿Te interesa alguno de ellos?"
                final_response = base_response + sugg_response
            else:
                final_response = base_response
            log_entry_data["bot_response"] = final_response
            log_entry_data["retrieved_context_summary"] = "RAG: No se recuperaron documentos."
        else:
            # Si hay documentos, llamamos al LLM para que sintetice la respuesta
            print(f"VALIDATION: {len(retrieved_docs)} documentos recuperados. Generando respuesta.")
            combine_docs_chain = load_qa_chain(llm=llm, chain_type="stuff", prompt=ChatPromptTemplate.from_template(qa_prompt_template))
            rag_result = await asyncio.to_thread(combine_docs_chain.invoke, {"input_documents": retrieved_docs, "question": question_for_retrieval})
            log_entry_data["bot_response"] = rag_result.get("output_text", "")
            # Loguear los documentos que SÍ se usaron
            summary_parts = [f"Doc: {doc.metadata.get('source_filename', 'N/A')}" for doc in retrieved_docs[:5]]
            log_entry_data["retrieved_context_summary"] = "\n".join(summary_parts)

    except Exception as e:
        log_entry_data["error_message"] = f"{type(e).__name__}: {e}"
        traceback.print_exc()

    finally:
        log_entry_data["response_time_ms"] = int((time.time() - start_time) * 1000)
        if not log_entry_data.get("error_message"):
            await asyncio.to_thread(unfiltered_history.add_messages, [HumanMessage(content=question), AIMessage(content=log_entry_data["bot_response"])])
        await crud_interaction_log.create_interaction_log(db_crud, log_entry_data)
        
    return ChatResponse(dni=user_dni_session_id, original_message=question, bot_response=log_entry_data.get("bot_response", "").strip(), metadata_details_json=log_entry_data.get("metadata_details_json", {}))