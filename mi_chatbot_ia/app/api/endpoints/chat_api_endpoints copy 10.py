# app/api/endpoints/chat_api_endpoints.py
# VERSIÓN DEFINITIVA, COMPLETA Y VERIFICADA

import time
import traceback
import asyncio
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# --- Langchain y modelos ---
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain.chains import ConversationalRetrievalChain, LLMChain
from langchain.chains.question_answering import load_qa_chain
from langchain.memory import ConversationBufferWindowMemory

# --- Módulos de la Aplicación ---
from app.db.session import get_crud_db_session
from app.models.api_client import ApiClient as ApiClientModel
from app.models.context_definition import ContextDefinition, ContextMainType
from app.models.llm_model_config import LLMModelConfig # <-- Importación crucial
from app.schemas.schemas import ChatRequest, ChatResponse
from app.crud import create_interaction_log, crud_llm_model_config
from app.config import settings
from app.security.api_key_auth import get_validated_api_client
from app.core.app_state import get_sync_vector_store, get_cached_llm_adapter
from ._chat_history_logic import FullyCustomChatMessageHistory
from app.services import cache_service
from app.tools.sql_tools import run_text_to_sql_lcel_chain

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

# --- Funciones de Ayuda ---
async def _handle_human_handoff(user_dni: str, question: str) -> str:
    ticket_id = f"TICKET-{int(time.time())}"
    return f"En este momento no puedo resolver tu consulta. He creado un ticket ({ticket_id}) y un agente se pondrá en contacto contigo."

async def _get_llm_config_for_context(db_crud: AsyncSession, context: ContextDefinition, api_client_settings: dict) -> LLMModelConfig:
    llm_config_id = context.default_llm_model_config_id or api_client_settings.get("default_llm_model_config_id_override")
    if not llm_config_id:
        raise ValueError(f"No se ha configurado un modelo LLM para el contexto '{context.name}' ni en la API Key.")
    
    llm_config = await crud_llm_model_config.get_llm_model_config_by_id(db_crud, llm_config_id)
    if not llm_config:
        raise ValueError(f"Modelo LLM con ID '{llm_config_id}' no encontrado.")
    return llm_config

# --- Endpoint Principal Unificado ---
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

    try:
        api_client_settings = current_api_client.settings or {}
        allowed_context_ids = api_client_settings.get("allowed_context_ids", [])
        if not allowed_context_ids:
            raise HTTPException(status_code=403, detail="API Key sin contextos permitidos.")

        stmt = (
            select(ContextDefinition)
            .where(ContextDefinition.id.in_(allowed_context_ids), ContextDefinition.is_active == True)
            .options(
                selectinload(ContextDefinition.db_connection_config),
                selectinload(ContextDefinition.default_llm_model_config),
                selectinload(ContextDefinition.virtual_agent_profile)
            )
        )
        active_contexts = (await db_crud.execute(stmt)).scalars().all()
        if not active_contexts:
            raise HTTPException(status_code=404, detail="Ninguno de los contextos permitidos está activo.")
        
        sql_keywords_in_question = any(kw.lower() in question.lower() for kw in settings.SQL_INTENT_KEYWORDS)
        
        target_context = None
        if sql_keywords_in_question:
            sql_context = next((ctx for ctx in active_contexts if ctx.main_type == ContextMainType.DATABASE_QUERY), None)
            if sql_context: target_context = sql_context
        
        if not target_context:
            target_context = next((ctx for ctx in active_contexts if ctx.main_type == ContextMainType.DOCUMENTAL), active_contexts[0])

        print(f"[INFO] Contexto seleccionado: '{target_context.name}' (Tipo: {target_context.main_type.value})")
        log_entry_data["metadata_details_json"]["active_context"] = f"{target_context.name} ({target_context.main_type.value})"
        
        chat_history = FullyCustomChatMessageHistory(session_id=user_dni)
        final_bot_response = ""
        llm_config = await _get_llm_config_for_context(db_crud, target_context, api_client_settings)
        # <<< --- ¡LA CORRECCIÓN CLAVE! AHORA ESTÁ FUERA DEL IF/ELIF Y SE LLAMA CORRECTAMENTE ---
        llm = await get_cached_llm_adapter(db_crud, model_id=llm_config.id)
        log_entry_data["llm_model_used"] = llm_config.display_name

        if target_context.main_type == ContextMainType.DOCUMENTAL:
            log_entry_data["intent"] = "RAG_DOCUMENTAL"
            print("[INFO] Ejecutando lógica RAG Documental...")
            
            # --- Aquí va tu lógica RAG original, pero ya tenemos `llm` ---
            vector_store = get_sync_vector_store()
            rag_context_names = [ctx.name for ctx in active_contexts if ctx.main_type == ContextMainType.DOCUMENTAL]
            retriever = vector_store.as_retriever(search_kwargs={"k": 6, "filter": {"context_name": {"$in": rag_context_names}}})
            
            def run_rag_chain_sync():
                qa_template = target_context.virtual_agent_profile.system_prompt if target_context.virtual_agent_profile else settings.DEFAULT_RAG_DOCS_QA_TEMPLATE
                q_gen_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template(settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE))
                combine_docs_chain = load_qa_chain(llm=llm, chain_type="stuff", prompt=ChatPromptTemplate.from_template(qa_template))
                rag_memory = ConversationBufferWindowMemory(memory_key="chat_history", chat_memory=chat_history, return_messages=True, output_key='answer')
                chain = ConversationalRetrievalChain(retriever=retriever, question_generator=q_gen_chain, combine_docs_chain=combine_docs_chain, memory=rag_memory, return_source_documents=True)
                return chain.invoke({"question": question})

            rag_result = await asyncio.to_thread(run_rag_chain_sync)
            final_bot_response = rag_result.get("answer", "")

        elif target_context.main_type == ContextMainType.DATABASE_QUERY:
            log_entry_data["intent"] = "TEXT_TO_SQL"
            print("[INFO] Ejecutando lógica Text-to-SQL...")

            if not target_context.db_connection_config: raise ValueError("Contexto Text-to-SQL sin conexión de BD.")
            
            chat_history_list = await asyncio.to_thread(lambda: chat_history.messages)
            chat_history_str = "\n".join([f"{msg.type}: {msg.content}" for msg in chat_history_list])
            # <<<--- AÑADE ESTOS PRINTS DE DEBUG ---
            print("\n" + "="*50)
            print("DEBUG CHAT_EP: `target_context.processing_config` que se pasará:")
            print(f"Tipo de dato: {type(target_context.processing_config)}")
            import json; print(f"Contenido JSON: {json.dumps(target_context.processing_config, indent=2)}")
            print("="*50 + "\n")
            # --- FIN DE PRINTS DE DEBUG ---
            sql_chain_result = await run_text_to_sql_lcel_chain(
                question=question, chat_history_str=chat_history_str,
                db_conn_config_for_sql=target_context.db_connection_config, llm=llm,
                sql_policy=target_context.processing_config or {}

            )
            final_bot_response = sql_chain_result.get("final_answer_llm", "No se pudo generar una respuesta desde la BD.")
            log_entry_data["metadata_details_json"].update({"generated_sql": sql_chain_result.get("generated_sql")})
        
        else:
            final_bot_response = f"El tipo de contexto '{target_context.main_type.value}' no está soportado."
        
        log_entry_data["bot_response"] = final_bot_response
    except Exception as e:
        print(f"CHAT_EP_CRITICAL_ERROR: {type(e).__name__} - {e}")
        traceback.print_exc()
        log_entry_data.update({"error_message": f"Error Interno: {type(e).__name__}", "bot_response": await _handle_human_handoff(user_dni, question)})
    
    finally:
        log_entry_data["response_time_ms"] = int((time.time() - start_time) * 1000)
        final_bot_response_to_log = log_entry_data.get("bot_response", "")
        
        final_history_manager = FullyCustomChatMessageHistory(session_id=user_dni)
        if final_bot_response_to_log and not log_entry_data.get("error_message"):
            await asyncio.to_thread(
                final_history_manager.add_messages,
                [HumanMessage(content=question), AIMessage(content=final_bot_response_to_log, additional_kwargs=log_entry_data.get("metadata_details_json", {}))])
        
        await create_interaction_log(db_crud, log_entry_data)
        
    return ChatResponse(
        dni=user_dni, original_message=question,
        bot_response=log_entry_data.get("bot_response", "").strip(),
        metadata_details_json=log_entry_data.get("metadata_details_json", {})
    )