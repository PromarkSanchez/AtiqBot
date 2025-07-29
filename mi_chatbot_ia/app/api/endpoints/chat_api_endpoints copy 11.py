# app/api/endpoints/chat_api_endpoints.py
# VERSIÓN FINAL-FINAL. BASADA EN TU CÓDIGO, SOLO CON LA LÓGICA DE DECISIÓN CORREGIDA.

import time
import traceback
import asyncio
from typing import List, Optional, Dict, Any
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

# Langchain Imports
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# Módulos de la Aplicación
from app.db.session import get_crud_db_session
from app.models.api_client import ApiClient as ApiClientModel
from app.models.context_definition import ContextDefinition, ContextMainType
from app.models.llm_model_config import LLMModelConfig
from app.models.virtual_agent_profile import VirtualAgentProfile
from app.schemas.schemas import ChatRequest, ChatResponse
from app.crud import (
    create_interaction_log, 
    crud_llm_model_config, 
    crud_virtual_agent_profile, 
    crud_context_definition
)
from app.config import settings
from app.security.api_key_auth import get_validated_api_client
from app.core.app_state import get_sync_vector_store, get_cached_llm_adapter
from ._chat_history_logic import FullyCustomChatMessageHistory
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

    try:
        api_client_settings = current_api_client.settings or {}
        allowed_context_ids = api_client_settings.get("allowed_context_ids", [])
        if not allowed_context_ids:
            raise HTTPException(status_code=403, detail="API Key sin contextos permitidos.")

        # --- Carga de Configuración y Enrutamiento (Tu lógica es perfecta) ---
        stmt = (
            select(ContextDefinition)
            .where(ContextDefinition.id.in_(allowed_context_ids), ContextDefinition.is_active == True)
            .options(
                joinedload(ContextDefinition.db_connection_config),
                joinedload(ContextDefinition.default_llm_model_config),
                joinedload(ContextDefinition.virtual_agent_profile)
            )
        )
        active_contexts = (await db_crud.execute(stmt)).scalars().all()
        if not active_contexts:
            raise HTTPException(status_code=404, detail="Ninguno de los contextos permitidos está activo.")
            
        is_sql_intent = any(kw.lower() in question.lower() for kw in settings.SQL_INTENT_KEYWORDS)
        target_context = None
        if is_sql_intent:
            sql_context = next((ctx for ctx in active_contexts if ctx.main_type == ContextMainType.DATABASE_QUERY), None)
            if sql_context: target_context = sql_context
        if not target_context:
            target_context = next((ctx for ctx in active_contexts if ctx.main_type == ContextMainType.DOCUMENTAL), active_contexts[0])

        log_entry_data["metadata_details_json"]["active_context"] = f"{target_context.name} ({target_context.main_type.value})"
        
        
        # --- Selección Final de Agente y LLM (Tu lógica es perfecta) ---
        vap_id_override = api_client_settings.get("default_virtual_agent_profile_id_override")
        llm_id_override = api_client_settings.get("default_llm_model_config_id_override")
        
        final_vap_id = vap_id_override or target_context.virtual_agent_profile_id
        if not final_vap_id: raise ValueError("No se pudo determinar un Perfil de Agente a usar.")
        agent_profile = await crud_virtual_agent_profile.get_virtual_agent_profile_by_id(db_crud, final_vap_id)
        if not agent_profile: raise ValueError(f"Perfil de Agente con ID {final_vap_id} no encontrado.")

        final_llm_id = llm_id_override or agent_profile.llm_model_config_id or target_context.default_llm_model_config_id
        if not final_llm_id: raise ValueError("No se pudo determinar un Modelo LLM a usar.")

        print(f"[INFO] Cargando configuración completa para LLM ID: {final_llm_id}")
        llm_config = await crud_llm_model_config.get_llm_model_config_by_id(db_crud, final_llm_id)
        if not llm_config: raise ValueError(f"CRÍTICO: El modelo LLM con ID {final_llm_id} no se encontró en la BD.")

        llm = await get_cached_llm_adapter(db_crud, model_config=llm_config)
        log_entry_data["llm_model_used"] = llm_config.display_name
        print(f"[INFO] Configuración Final: Perfil='{agent_profile.name}', LLM='{log_entry_data['llm_model_used']}'")
        
        # --- EJECUCIÓN DE LA CADENA CORRECTA (LÓGICA CORREGIDA) ---
        chat_history_manager = FullyCustomChatMessageHistory(session_id=user_dni)
        chat_history_list = await asyncio.to_thread(lambda: chat_history_manager.messages)
        final_bot_response = ""

        # --- EL CEREBRO DE DECISIÓN (AHORA ESTRUCTURADO CORRECTAMENTE) ---
        
        # ETAPA 1: Saludo inicial
        if not chat_history_list and question == "__INICIAR_CHAT__":
            print("[BRAIN] Decisión: ETAPA 1 - Saludo")
            log_entry_data["intent"] = "GREETING"
            prompt_to_use = agent_profile.greeting_prompt
            if not prompt_to_use:
                raise ValueError(f"El perfil '{agent_profile.name}' no tiene 'greeting_prompt' definido.")
            
            chain = ChatPromptTemplate.from_template(prompt_to_use) | llm | StrOutputParser()
            final_bot_response = await chain.ainvoke({})
        
        # ETAPA 2: Confirmación de Nombre
        elif chat_history_list and agent_profile.name_confirmation_prompt and \
             ("cómo te gustaría que te llame" in chat_history_list[-1].content.lower() or "¿cómo te llamas?" in chat_history_list[-1].content.lower()):
            print("[BRAIN] Decisión: ETAPA 2 - Confirmación de Nombre")
            log_entry_data["intent"] = "NAME_CONFIRMATION"
            prompt_to_use = agent_profile.name_confirmation_prompt
            chain = ChatPromptTemplate.from_template(prompt_to_use) | llm | StrOutputParser()
            final_bot_response = await chain.ainvoke({"user_input": question})

        # ETAPA 3: Resolución de Consultas (tu lógica original va aquí adentro)
        else:
            print(f"[BRAIN] Decisión: ETAPA 3 - Resolución de Consulta tipo {target_context.main_type.value}")
            if target_context.main_type == ContextMainType.DOCUMENTAL:
                log_entry_data["intent"] = "RAG_DOCUMENTAL"
                print("[INFO] Ejecutando lógica RAG Documental con LCEL...")

                formatted_history = "\n".join([f"{'Usuario' if msg.type == 'human' else 'Asistente'}: {msg.content}" for msg in chat_history_list])
                context_str = ""
                retrieved_docs = []

                if question != "__INICIAR_CHAT__": # Asegura que no hagamos RAG para el saludo
                    vector_store = get_sync_vector_store()
                    rag_context_names = [ctx.name for ctx in active_contexts if ctx.main_type == ContextMainType.DOCUMENTAL]
                    retriever = vector_store.as_retriever(search_kwargs={"k": 6, "filter": {"context_name": {"$in": rag_context_names}}})
                    retrieved_docs = await asyncio.to_thread(retriever.invoke, question)
                    context_str = "\n\n---\n\n".join([doc.page_content for doc in retrieved_docs])

                log_entry_data["retrieved_context_summary"] = f"Recuperados {len(retrieved_docs)} chunks."

                system_prompt_template = agent_profile.system_prompt
                rag_prompt = ChatPromptTemplate.from_template(system_prompt_template)
                
                rag_chain = (
                    RunnablePassthrough.assign(chat_history=lambda x: formatted_history, context=lambda x: context_str)
                    | rag_prompt | llm | StrOutputParser()
                )
                final_bot_response = await rag_chain.ainvoke({"question": question})

            elif target_context.main_type == ContextMainType.DATABASE_QUERY:
                log_entry_data["intent"] = "TEXT_TO_SQL"
                print("[INFO] Ejecutando lógica Text-to-SQL...")
                if not target_context.db_connection_config: raise ValueError("Contexto Text-to-SQL sin conexión de BD.")
                
                chat_history_str = "\n".join([f"{msg.type}: {msg.content}" for msg in chat_history_list])
                
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