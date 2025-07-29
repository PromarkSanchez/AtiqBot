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
        
        # --- NUEVO BLOQUE DE LÓGICA DE VISIBILIDAD Y LOGIN ---

        # 1. Obtener contextos REALMENTE activos para el nivel de acceso actual
        if chat_request.is_authenticated_user:
            result = await db_crud.execute(stmt_base)
            active_contexts = result.scalars().unique().all()
        else: # Usuario invitado
            public_contexts_query = stmt_base.filter(ContextDefinition.is_public == True)
            result = await db_crud.execute(public_contexts_query)
            active_contexts = result.scalars().unique().all()
            
            # 2. ANTES de hacer cualquier otra cosa, si el invitado pregunta algo
            # que suena a base de datos Y NO hay contextos públicos de BD para él...
            db_intent_keywords = getattr(settings, 'DB_INTENT_KEYWORDS', 
                ["nota", "horario", "promedio", "mis ", "cuántos", "lista"]) # 'mis ' es clave
            
            is_potential_private_query = any(kw.lower() in question.lower() for kw in db_intent_keywords)
            
            # Comprobamos si no hay contextos de BD *públicos*
            has_no_public_db_contexts = not any(c.main_type == ContextMainType.DATABASE_QUERY for c in active_contexts)

            if is_potential_private_query and has_no_public_db_contexts:
                # La pregunta suena a privada, y no tenemos acceso público.
                # Verifiquemos si un contexto privado SÍ existe.
                private_db_contexts_exist_query = stmt_base.filter(ContextDefinition.main_type == ContextMainType.DATABASE_QUERY, ContextDefinition.is_public == False)
                count_result = await db_crud.execute(select(func.count()).select_from(private_db_contexts_exist_query.subquery()))

                if count_result.scalar_one() > 0:
                    # ¡Bingo! Hay un contexto privado que podría responder. Pedimos login.
                    log_entry_data.update({
                        "intent": "AUTH_REQUIRED_PROMPT",
                        "bot_response": "Para consultas sobre información personal como tus notas, necesito que inicies sesión. Así puedo proteger tus datos.",
                        "metadata_details_json": {"action_required": "request_login"}
                    })
                    raise StopIteration("Usuario invitado requiere login para una consulta de tipo BD.")

        # 3. Si después de todo no hay contextos activos, es un fallo
        if not active_contexts:
            raise HTTPException(404, "Lo siento, no tengo información disponible para tu consulta y nivel de acceso.")
        
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
    
        # =========================================================
        # INICIO DE LA MÁQUINA DE ESTADOS COMPLETA Y CORREGIDA
        # =========================================================

        # ETAPA 1: Saludo inicial (cuando el chat es nuevo)
        if not has_history and question == "__INICIAR_CHAT__":
            log_entry_data["intent"] = "GREETING_STAGE"
            if not agent_profile.greeting_prompt: 
                raise ValueError("El Perfil de Agente no tiene configurado un 'greeting_prompt'.")
            
            user_name_for_prompt = chat_request.user_name or "Usuario"
            try:
                final_bot_response = agent_profile.greeting_prompt.format(user_name=user_name_for_prompt)
            except KeyError:
                print("WARN: 'greeting_prompt' no contiene '{user_name}'. Usando prompt como texto literal.")
                final_bot_response = agent_profile.greeting_prompt
            
            if agent_profile.name_confirmation_prompt:
                cache_service.set_cache(f"chat_state:{session_id}", CONV_STATE_AWAITING_NAME, ttl_seconds=300)

        # ETAPA 2: Captura del nombre del usuario (después del saludo)
        elif current_conv_state == CONV_STATE_AWAITING_NAME:
            log_entry_data["intent"] = "NAME_CAPTURE_STAGE"
            user_provided_name = question.strip()
            
            # Guardamos el nombre del usuario en la caché para usarlo después
            cache_service.set_cache(f"user_name:{session_id}", user_provided_name, ttl_seconds=settings.CACHE_EXPIRATION_SECONDS)

            if not agent_profile.name_confirmation_prompt:
                raise ValueError("El Perfil de Agente no tiene configurado un 'name_confirmation_prompt'.")
            
            try:
                final_bot_response = agent_profile.name_confirmation_prompt.format(user_provided_name=user_provided_name)
            except KeyError:
                print("WARN: 'name_confirmation_prompt' no contiene '{user_provided_name}'. Usando prompt como texto literal.")
                final_bot_response = agent_profile.name_confirmation_prompt
            
            # Limpiamos el estado para que la próxima pregunta pase a la Etapa 3
            cache_service.delete_cache(f"chat_state:{session_id}")

        # =========================================================
        # ETAPA 3: Resolución de Consulta (Lógica principal)
        # =========================================================
        else:
            # --- 1. Separar los contextos disponibles por tipo ---
            db_contexts = [c for c in active_contexts if c.main_type == ContextMainType.DATABASE_QUERY]
            doc_contexts = [c for c in active_contexts if c.main_type == ContextMainType.DOCUMENTAL]
            
            target_context = None

            # --- 2. Estrategia de Selección de Contexto ---
            db_intent_keywords = getattr(settings, 'DB_INTENT_KEYWORDS', 
                ["nota", "horario", "promedio", "consultar", "cuántos", "lista", "mis "])

            is_explicit_db_intent = any(kw.lower() in question.lower() for kw in db_intent_keywords)

            if is_explicit_db_intent and db_contexts:
                target_context = db_contexts[0]
            elif doc_contexts:
                target_context = doc_contexts[0]
            elif active_contexts: # Fallback si no hay documentales
                target_context = active_contexts[0]
            else:
                raise HTTPException(status_code=404, detail="No se encontró ningún contexto aplicable para tu consulta.")
            
            print(f"SELECTOR: Contexto seleccionado: '{target_context.name}' (Tipo: {target_context.main_type.value})")

            # --- 3. Ejecutar la cadena correspondiente al contexto seleccionado ---
            
            if target_context.main_type == ContextMainType.DOCUMENTAL:
                log_entry_data["intent"] = "RAG_DOCUMENTAL"
                user_name_from_cache = cache_service.get_cache(f"user_name:{session_id}") or chat_request.user_name or "Usuario"
                
                def run_rag_chain_sync():
                    condense_question_prompt = PromptTemplate.from_template(settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE)
                    answer_prompt = ChatPromptTemplate.from_template(agent_profile.system_prompt)
                    standalone_question_chain = condense_question_prompt | llm | StrOutputParser()
                    
                    vector_store = get_sync_vector_store()
                    # Usa la lista `doc_contexts` que ya filtramos arriba para mayor eficiencia
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
                if not target_context.db_connection_config:
                    raise ValueError("El contexto DATABASE_QUERY no tiene una conexión de BD configurada.")
                
                chat_history_str = get_buffer_string(chat_history_list)

                db_query_result = await run_db_query_chain(
                    question=question,
                    chat_history_str=chat_history_str,
                    db_conn_config=target_context.db_connection_config,
                    processing_config=target_context.processing_config or {},
                    llm=llm,
                    user_dni=chat_request.user_dni
                )
                
                final_bot_response = db_query_result.get("final_answer", "No pude obtener una respuesta de la base de datos.")
                log_entry_data["intent"] = db_query_result.get("intent", "DATABASE_QUERY_ERROR")
                log_entry_data["metadata_details_json"].update(db_query_result.get("metadata", {}))

                # Si necesitamos pedir clarificación, aquí podríamos guardar el estado en Redis en un futuro.
                # Por ahora, simplemente devolvemos la pregunta que nos dio sql_tools.
                
        log_entry_data["bot_response"] = final_bot_response

        if not has_history and final_bot_response and log_entry_data.get("intent") not in ["GREETING_STAGE", "NAME_CAPTURE_STAGE", "AUTH_REQUIRED_PROMPT"]:
            response_to_cache = {"bot_response": final_bot_response, "metadata_details_json": log_entry_data.get("metadata_details_json", {})}
            cache_service.set_cached_response(...)

                
    
    ### CAMBIO 4: Manejo de Excepciones mejorado y más robusto ###
    # --- INICIO DEL NUEVO BLOQUE DE MANEJO DE EXCEPCIONES ---
    except StopIteration:
        # Este bloque AHORA captura nuestra señal interna 'StopIteration'
        # La respuesta y los metadatos ya fueron establecidos en `log_entry_data`
        # antes de lanzar la excepción. Así que no hacemos nada aquí, solo
        # permitimos que el flujo continúe hacia el `finally`.
        print("[INFO] Flujo de chat terminado anticipadamente por StopIteration (ej. AUTH_REQUIRED).")
    
    except HTTPException as e:
        # Mantenemos este para manejar errores 4xx y relanzarlos.
        log_entry_data["error_message"] = f"HTTP Error: {e.status_code} - {e.detail}"
        log_entry_data["bot_response"] = e.detail
        await create_interaction_log(db_crud, log_entry_data)
        raise e

    except Exception as e:
        # Este bloque ahora solo captura errores REALES e inesperados.
        print(f"CHAT_EP_CRITICAL_ERROR: Ocurrió un error inesperado: {type(e).__name__} - {e}")
        traceback.print_exc()
        handoff_result = await _handle_human_handoff(user_log_identifier, question)
        log_entry_data["error_message"] = f"Internal Error: {type(e).__name__}"
        log_entry_data["bot_response"] = handoff_result["response_text"]

    
# ... (todo tu código hasta el inicio del bloque finally) ...

    finally:
        log_entry_data["response_time_ms"] = int((time.time() - start_time) * 1000)
        
        # --- INICIO DE LA CORRECCIÓN DE SERIALIZACIÓN ---
        # "Sanitizamos" los metadatos para asegurar que son compatibles con JSONB en la BD
        # Esto convierte tipos de datos complejos (como datetime) en strings.
        try:
            metadata_to_log = log_entry_data.get("metadata_details_json", {})
            # El truco: lo convertimos a un string JSON y lo volvemos a parsear.
            # `default=str` maneja cualquier tipo de dato no serializable convirtiéndolo a su representación de string.
            log_entry_data["metadata_details_json"] = json.loads(json.dumps(metadata_to_log, default=str))
        except Exception as e_json:
            print(f"ERROR_SERIALIZATION: No se pudieron sanitizar los metadatos para el log: {e_json}")
            # Si falla la sanitización, guardamos el error en su lugar para no perder el log.
            log_entry_data["metadata_details_json"] = {"serialization_error": str(e_json)}
        # --- FIN DE LA CORRECCIÓN DE SERIALIZACIÓN ---
        
        # El resto de la lógica del finally se mantiene igual
        should_log_history_and_db = True
        if "error_message" in log_entry_data:
            err_msg = log_entry_data["error_message"]
            if isinstance(err_msg, str) and err_msg.startswith("HTTP Error"):
                should_log_history_and_db = False

        if should_log_history_and_db:
            final_response_for_history = log_entry_data.get("bot_response", "")
            if final_response_for_history and log_entry_data.get("error_message") is None:
                await asyncio.to_thread(history_manager.add_messages,
                    [HumanMessage(content=question), AIMessage(content=final_response_for_history)])
            
            # Ahora esta llamada es segura
            await create_interaction_log(db_crud, log_entry_data)

    return ChatResponse(
        session_id=session_id, original_message=question,
        bot_response=log_entry_data.get("bot_response", "").strip(),
        metadata_details_json=log_entry_data.get("metadata_details_json", {})
    )