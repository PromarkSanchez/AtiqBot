# app/api/endpoints/chat_api_endpoints.py
import os
import time
import traceback
from typing import List, Optional, Dict, Any
import asyncio
import json

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy import select, create_engine, Column, Integer, Text, DateTime, String, JSON as SQLA_JSON_TYPE
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession

# Langchain Imports
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, messages_from_dict, message_to_dict
from langchain_core.documents import Document as LangchainDocument
from langchain_postgres.vectorstores import PGVector
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain.memory import ConversationBufferWindowMemory
from langchain.chains import ConversationalRetrievalChain
from langchain.chains.llm import LLMChain
from langchain.chains.question_answering import load_qa_chain
from langchain.chains import RetrievalQA
# Application Specific Imports
from app.db.session import get_crud_db_session
from app.models.api_client import ApiClient as ApiClientModel
from app.models.llm_model_config import LLMModelConfig
from app.models.context_definition import ContextDefinition, ContextMainType
from app.models.db_connection_config import DatabaseConnectionConfig
from app.models.human_agent import HumanAgent
from app.schemas.schemas import ChatRequest, ChatResponse
from app.crud import crud_interaction_log, crud_context_definition, crud_human_agent, crud_llm_model_config
from app.crud.crud_db_connection import get_db_connection_by_id_sync
from app.config import settings
from app.tools.sql_tools import run_text_to_sql_lcel_chain
from app.security.api_key_auth import get_validated_api_client
from app.llm_integrations.langchain_llm_adapter import get_langchain_llm_adapter
from app.crud import crud_virtual_agent_profile

print("CHAT_EP_DEBUG: chat_api_endpoints.py module loading...")

# --- Constantes del Módulo ---
MODEL_NAME_SBERT_FOR_EMBEDDING = settings.MODEL_NAME_SBERT_FOR_EMBEDDING
PGVECTOR_CHAT_COLLECTION_NAME = settings.PGVECTOR_CHAT_COLLECTION_NAME
MAX_RETRIEVED_CHUNKS_RAG = settings.MAX_RETRIEVED_CHUNKS_RAG
CHAT_HISTORY_TABLE_NAME = settings.CHAT_HISTORY_TABLE_NAME
DW_CONTEXT_CONFIG_NAME = settings.DW_CONTEXT_CONFIG_NAME
CHAT_HISTORY_WINDOW_SIZE_RAG = settings.CHAT_HISTORY_WINDOW_SIZE_RAG
CHAT_HISTORY_WINDOW_SIZE_SQL = settings.CHAT_HISTORY_WINDOW_SIZE_SQL
LANGCHAIN_VERBOSE_FLAG = settings.LANGCHAIN_VERBOSE
SQL_INTENT_KEYWORDS = settings.SQL_INTENT_KEYWORDS
DW_TABLE_PREFIXES_FOR_INTENT = settings.DW_TABLE_PREFIXES_FOR_INTENT
DEFAULT_HANDOFF_MESSAGE_TO_USER = settings.DEFAULT_HANDOFF_MESSAGE_TO_USER \
    if hasattr(settings, 'DEFAULT_HANDOFF_MESSAGE_TO_USER') \
    else "Entendido. No pude resolver tu consulta. Te pondré en contacto con un especialista."
TEAMS_DEEPLINK_BASE_USER = "https://teams.microsoft.com/l/chat/0/0?users="
HANDOFF_KEYWORDS = ["humano", "agente", "especialista", "persona", "hablar con", "derivar", "ayuda directa", "soporte técnico"]
GENERIC_NO_ANSWER_PHRASES = ["no tengo información", "no sé", "no pude encontrar", "no se encontraron contextos", "datos no disponibles", "disculpa, no encuentro eso"]

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

# --- Instancias Singleton y Funciones Auxiliares ---
_vector_store_instance_sync: Optional[PGVector] = None
_lc_sbert_embeddings_instance: Optional[SentenceTransformerEmbeddings] = None
_sync_history_engine = None 
_SyncHistorySessionLocalFactory = None 

def get_lc_sbert_embeddings() -> SentenceTransformerEmbeddings:
    global _lc_sbert_embeddings_instance
    if _lc_sbert_embeddings_instance is None:
        print(f"CHAT_EP_INFO: Creando SBERT Embeddings: {MODEL_NAME_SBERT_FOR_EMBEDDING}")
        _lc_sbert_embeddings_instance = SentenceTransformerEmbeddings(model_name=MODEL_NAME_SBERT_FOR_EMBEDDING)
    return _lc_sbert_embeddings_instance

def get_chat_vector_store_sync() -> PGVector:
    global _vector_store_instance_sync
    if _vector_store_instance_sync is None:
        print(f"CHAT_EP_INFO: Creando PGVector (síncrono): '{PGVECTOR_CHAT_COLLECTION_NAME}'")
        lc_embeddings = get_lc_sbert_embeddings()
        sync_vector_db_url = settings.SYNC_DATABASE_VECTOR_URL
        if not sync_vector_db_url: raise ValueError("SYNC_DATABASE_VECTOR_URL no configurada.")
        _vector_store_instance_sync = PGVector(connection=sync_vector_db_url, embeddings=lc_embeddings, collection_name=PGVECTOR_CHAT_COLLECTION_NAME, use_jsonb=True, async_mode=False, create_extension=False)
        print(f"CHAT_EP_INFO: PGVector instance creada.")
    return _vector_store_instance_sync

# --- Implementación del Historial de Chat (SIN CAMBIOS) ---
_HistoryBase = declarative_base()
class _HistoryMessageORM(_HistoryBase):
    __tablename__ = CHAT_HISTORY_TABLE_NAME
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(255), nullable=False, index=True)
    message = Column(SQLA_JSON_TYPE, nullable=False)
    def __repr__(self) -> str: return f"<HistoryMessageORM(id={self.id}, session_id='{self.session_id}')>"

def get_sync_history_session() -> Session:
    global _sync_history_engine, _SyncHistorySessionLocalFactory
    if _sync_history_engine is None:
        sync_db_url = settings.SYNC_DATABASE_CRUD_URL
        if not sync_db_url: raise ValueError("SYNC_DATABASE_CRUD_URL no configurada para historial.")
        _sync_history_engine = create_engine(sync_db_url, echo=False) 
        _HistoryBase.metadata.create_all(_sync_history_engine) 
        _SyncHistorySessionLocalFactory = sessionmaker(autocommit=False, autoflush=False, bind=_sync_history_engine)
        print(f"CHAT_EP_INFO: Engine/SessionFactory SÍNCRONOS historial (re)creados.")
    if not _SyncHistorySessionLocalFactory: raise RuntimeError("SyncHistorySessionLocalFactory no inicializada.")
    return _SyncHistorySessionLocalFactory()

class FullyCustomChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, session_id: str):
        if not session_id: raise ValueError("session_id es requerido para el historial.")
        self.session_id = session_id

    @property
    def messages(self) -> List[BaseMessage]:
        db_session: Session = get_sync_history_session()
        try:
            stmt = select(_HistoryMessageORM).where(_HistoryMessageORM.session_id == self.session_id).order_by(_HistoryMessageORM.id.asc())
            orm_messages = db_session.execute(stmt).scalars().all()
            converted_messages: List[BaseMessage] = []
            for orm_msg in orm_messages:
                if isinstance(orm_msg.message, dict): converted_messages.extend(messages_from_dict([orm_msg.message]))
                elif isinstance(orm_msg.message, str):
                    try: converted_messages.extend(messages_from_dict([json.loads(orm_msg.message)]))
                    except json.JSONDecodeError: print(f"HIST_ERROR: Mensaje (str) ID {orm_msg.id} no es JSON válido.")
                else: print(f"HIST_WARNING: Mensaje ID {orm_msg.id} tipo inesperado: {type(orm_msg.message)}")
            if LANGCHAIN_VERBOSE_FLAG: print(f"HIST_DEBUG (FullyCustom): Recuperados {len(converted_messages)} mensajes para session '{self.session_id}'.")
            return converted_messages
        except Exception as e: print(f"HIST_ERROR (FullyCustom/get): {e}"); db_session.rollback(); raise
        finally: db_session.close()
    def add_messages(self, messages: List[BaseMessage]) -> None:
        db_session: Session = get_sync_history_session()
        try:
            for msg in messages: db_session.add(_HistoryMessageORM(session_id=self.session_id, message=message_to_dict(msg)))
            db_session.commit()
        finally: db_session.close()
    def clear(self) -> None:
        db_session: Session = get_sync_history_session()
        try: db_session.execute(_HistoryMessageORM.__table__.delete().where(_HistoryMessageORM.session_id == self.session_id)); db_session.commit()
        finally: db_session.close()

class ContextAwareFilteredHistory(BaseChatMessageHistory):
    def __init__(self, underlying_history: FullyCustomChatMessageHistory, allowed_context_names_current: List[str]):
        self.underlying_history = underlying_history
        self.allowed_context_names_current_set = set(allowed_context_names_current)
        self.session_id = underlying_history.session_id
        print(f"ContextAwareFilteredHistory: Instanciada. Wraps session '{self.session_id}'. Contextos actuales PERMITIDOS: {self.allowed_context_names_current_set}")

    @property
    def messages(self) -> List[BaseMessage]:
        all_messages = self.underlying_history.messages
        filtered_messages: List[BaseMessage] = []; idx = 0
        while idx < len(all_messages):
            current_msg = all_messages[idx]; human_msg_to_add: Optional[BaseMessage] = None; ai_msg_to_add: Optional[BaseMessage] = None
            if current_msg.type == "human":
                human_msg_to_add = current_msg
                if (idx + 1) < len(all_messages) and all_messages[idx+1].type == "ai":
                    ai_candidate = all_messages[idx+1]
                    sources_str = ai_candidate.additional_kwargs.get("source_contexts_names", "")
                    if sources_str:
                        sources_set = set(s.strip() for s in sources_str.split(',') if s.strip())
                        if not self.allowed_context_names_current_set.intersection(sources_set) and len(sources_set) > 0:
                            print(f"CONTEXT_AWARE_HIST_FILTER (SKIP): Omitiendo par Human-AI. AI_Contexts='{sources_set}', Allowed='{self.allowed_context_names_current_set}'")
                            human_msg_to_add = None 
                        else: ai_msg_to_add = ai_candidate
                    else: ai_msg_to_add = ai_candidate
                    idx += 2
                else: idx += 1
                if human_msg_to_add: filtered_messages.append(human_msg_to_add)
                if ai_msg_to_add: filtered_messages.append(ai_msg_to_add)
            else: filtered_messages.append(current_msg); idx += 1
        print(f"ContextAwareFilteredHistory: Originales={len(all_messages)}, Filtrados={len(filtered_messages)} para session '{self.session_id}'.")
        return filtered_messages
    def add_messages(self, messages: List[BaseMessage]) -> None: self.underlying_history.add_messages(messages)
    def clear(self) -> None: self.underlying_history.clear()

# --- Placeholders para Notificación de Handoff (SIN CAMBIOS) ---
async def select_human_agent_for_handoff(db_for_crud: AsyncSession, group_id: int) -> Optional[HumanAgent]:
    group = await crud_human_agent.get_human_agent_group_by_id(db_for_crud, group_id=group_id, load_agents=True)
    if group and group.agents:
        for agent in group.agents:
            if agent.is_active and agent.teams_id: return agent
    return None

async def create_ticket_for_handoff(group_name: str, summary_for_agent: str) -> str:
    print(f"HANDOFF_TICKET (SIMULACIÓN): Creando ticket para grupo '{group_name}'. Resumen: {summary_for_agent[:100]}...")
    return f"TICKET_SIM_{int(time.time())}"


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
    print(f"CHAT_EP_INFO: Solicitud Chat: Cliente='{current_api_client.name}', UserID='{user_dni_session_id}', Pregunta='{question[:100]}...'")

    # --- LÓGICA DINÁMICA DE LLM ---
    llm_model_config: Optional[LLMModelConfig] = None
    llm_override_id = api_client_settings.get("default_llm_model_config_id_override")
    
    if llm_override_id:
        print(f"CHAT_EP_INFO: Usando LLM override. Config ID: {llm_override_id}")
        llm_model_config = await crud_llm_model_config.get_llm_model_config_by_id(db_crud, llm_override_id)
        if not llm_model_config:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"LLM config ID {llm_override_id} definido en cliente API no encontrado.")
    
    if not llm_model_config:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="El cliente API debe tener un modelo LLM configurado.")
    if not llm_model_config.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"El modelo LLM '{llm_model_config.display_name}' está inactivo.")

    try:
        llm = get_langchain_llm_adapter(llm_model_config)
        print(f"CHAT_EP_INFO: LLM '{llm_model_config.display_name}' instanciado para LangChain.")
    except (NotImplementedError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    # --- FIN LÓGICA DINÁMICA DE LLM ---

    log_entry_data: Dict[str, Any] = {
        "user_dni": user_dni_session_id, "api_client_name": current_api_client.name, "user_message": question,
        "llm_model_used": llm_model_config.display_name, "bot_response": "[Respuesta no generada por error]",
        "intent": "UNKNOWN", "metadata_details_json": {"used_sources": []}
    }

    context_def_dw_instance_orm: Optional[ContextDefinition] = None
    final_rag_target_context_names: List[str] = [] 

    try:
        allowed_context_ids_from_client: List[int] = api_client_settings.get("allowed_context_ids", [])
        resolved_api_client_allowed_context_names: List[str] = []
        if allowed_context_ids_from_client:
            stmt = select(ContextDefinition.name).filter(ContextDefinition.id.in_(allowed_context_ids_from_client), ContextDefinition.is_active == True)
            result = await db_crud.execute(stmt)
            resolved_api_client_allowed_context_names = result.scalars().all()
        print(f"CHAT_EP_INFO (pre-historial): Contextos permitidos para ApiClient: {resolved_api_client_allowed_context_names or 'NINGUNO'}")

        unfiltered_chat_history = FullyCustomChatMessageHistory(session_id=user_dni_session_id)
        chat_message_history_for_chain = ContextAwareFilteredHistory(unfiltered_chat_history, resolved_api_client_allowed_context_names)
        
        if LANGCHAIN_VERBOSE_FLAG:
            try: await asyncio.to_thread(lambda: list(chat_message_history_for_chain.messages))
            except Exception as e: print(f"CHAT_EP_WARNING: Error cargando hist. filtrado (verbose): {e}")

        question_lower = question.lower()
        
        force_handoff_by_keyword = any(k in question_lower for k in HANDOFF_KEYWORDS)
        target_handoff_group_id_cfg = api_client_settings.get("human_handoff_agent_group_id")
        
        print(f"HANDOFF_DEBUG: force_handoff_by_keyword = {force_handoff_by_keyword} (basado en '{question_lower}')")
        print(f"HANDOFF_DEBUG: target_handoff_group_id_cfg del ApiClient = {target_handoff_group_id_cfg}")
        
        if force_handoff_by_keyword and target_handoff_group_id_cfg:
            log_entry_data["intent"] = "HUMAN_HANDOFF_KEYWORD"
            hist_msgs_summary = await asyncio.to_thread(lambda: list(chat_message_history_for_chain.messages[-6:]))
            summary = f"Usuario '{user_dni_session_id}' solicita derivación. Pregunta: '{question}'.\nHistorial: " + "\n".join([f"- {m.type}: {m.content}" for m in hist_msgs_summary])
            
            selected_agent = await select_human_agent_for_handoff(db_crud, target_handoff_group_id_cfg)
            if selected_agent and selected_agent.teams_id:
                log_entry_data["bot_response"] = f"Entendido. Te contactaré con {selected_agent.full_name}. Por favor, espera."
                log_entry_data["metadata_details_json"]["handoff_info"] = {"type":"TEAMS_AGENT", "agent_name":selected_agent.full_name, "group_id":target_handoff_group_id_cfg}
            else:
                group = await crud_human_agent.get_human_agent_group_by_id(db_crud, group_id=target_handoff_group_id_cfg)
                ticket_id = await create_ticket_for_handoff(group.name if group else f"Grupo ID {target_handoff_group_id_cfg}", summary)
                log_entry_data["bot_response"] = f"Entendido. He creado un ticket ({ticket_id}) para que un especialista te contacte."
                log_entry_data["metadata_details_json"]["handoff_info"] = {"type":"TICKET", "group_id":target_handoff_group_id_cfg, "ticket_id":ticket_id}
        else:
            is_sql_intent_heuristic = any(k in question_lower for k in SQL_INTENT_KEYWORDS) or any(p.lower() in question_lower for p in DW_TABLE_PREFIXES_FOR_INTENT)
            is_dw_context_allowed = DW_CONTEXT_CONFIG_NAME in resolved_api_client_allowed_context_names
            attempt_sql_query_flag = is_dw_context_allowed and is_sql_intent_heuristic
            print(f"CHAT_EP_DEBUG_ROUTE: IntenciónSQL? {is_sql_intent_heuristic} | DWPermitido? {is_dw_context_allowed} | IntentarSQL? {attempt_sql_query_flag}")

            if is_dw_context_allowed:
                 context_def_dw_instance_orm = await crud_context_definition.get_context_definition_by_name(db_crud, name=DW_CONTEXT_CONFIG_NAME, load_relations_fully=True)

            if attempt_sql_query_flag and context_def_dw_instance_orm and context_def_dw_instance_orm.is_active and \
               context_def_dw_instance_orm.main_type == ContextMainType.DATABASE_QUERY and context_def_dw_instance_orm.db_connection_config_id:
                log_entry_data["intent"] = "SQL_QUERY_DW"
                db_conn_orm: Optional[DatabaseConnectionConfig] = get_db_connection_by_id_sync(context_def_dw_instance_orm.db_connection_config_id)
                if not db_conn_orm: raise ValueError(f"Config BD ID '{context_def_dw_instance_orm.db_connection_config_id}' para DW no encontrada.")
                sql_policy_from_cfg = (context_def_dw_instance_orm.processing_config or {}).get("sql_select_policy", {})
                
                sql_hist_str = ""
                sql_output = await run_text_to_sql_lcel_chain(question=question, chat_history_str=sql_hist_str, db_conn_config_for_sql=db_conn_orm, llm=llm, sql_policy=sql_policy_from_cfg)
                log_entry_data["bot_response"] = sql_output["final_answer_llm"]
                log_entry_data["metadata_details_json"]["used_sources"].append({"type": "DATABASE_QUERY_RESULT", "context_name": context_def_dw_instance_orm.name, "source_identifier": "Direct_SQL_Execution", "details": {"generated_sql": sql_output.get('generated_sql'), "dw_connection_used": db_conn_orm.name }})
                log_entry_data["retrieved_context_summary"] = f"SQL: {str(sql_output.get('generated_sql'))[:70]}..."
            else:
                # ===============================================
                # ============ INICIO RAMA RAG ==================
                # ===============================================
                log_entry_data["intent"] = "RAG_DOCS_OR_SCHEMA"
                primary_context_for_rag: Optional[ContextDefinition] = None
                
                for ctx_name in resolved_api_client_allowed_context_names:
                    current_ctx_orm: Optional[ContextDefinition] = None
                    if ctx_name == DW_CONTEXT_CONFIG_NAME and context_def_dw_instance_orm: current_ctx_orm = context_def_dw_instance_orm
                    else: current_ctx_orm = await crud_context_definition.get_context_definition_by_name(db_crud, name=ctx_name)
                    
                    if not current_ctx_orm or not current_ctx_orm.is_active: continue
                    
                    is_documental_rag = current_ctx_orm.main_type == ContextMainType.DOCUMENTAL
                    is_schema_rag = (current_ctx_orm.name == DW_CONTEXT_CONFIG_NAME and not attempt_sql_query_flag)

                    if is_documental_rag or is_schema_rag:
                        final_rag_target_context_names.append(ctx_name)
                        if not primary_context_for_rag: primary_context_for_rag = current_ctx_orm
                
                print(f"CHAT_EP_INFO: Contextos finales para RAG: {final_rag_target_context_names or 'NINGUNO'}")

                if not final_rag_target_context_names:
                    log_entry_data["bot_response"] = "No encontré contextos documentales para tu consulta."
                else:
                    # ===== Lógica de carga dinámica del Agente Virtual =====
                    virtual_agent_profile = None
                    vap_id_override = api_client_settings.get("default_virtual_agent_profile_id_override")
                    
                    if vap_id_override:
                        print(f"AGENT_PROFILE: Buscando override de ApiClient. ID: {vap_id_override}")
                        virtual_agent_profile = await crud_virtual_agent_profile.get_virtual_agent_profile_by_id(db_crud, vap_id_override)
                    elif primary_context_for_rag and primary_context_for_rag.virtual_agent_profile_id:
                        vap_id_context = primary_context_for_rag.virtual_agent_profile_id
                        print(f"AGENT_PROFILE: Buscando perfil del contexto '{primary_context_for_rag.name}'. ID: {vap_id_context}")
                        virtual_agent_profile = await crud_virtual_agent_profile.get_virtual_agent_profile_by_id(db_crud, vap_id_context)
                    
                    # ===== Selección de las plantillas de prompt =====
                    condense_template = settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE
                    docs_qa_template = settings.DEFAULT_RAG_DOCS_QA_TEMPLATE # Valor por defecto
                    
                    if virtual_agent_profile and virtual_agent_profile.is_active and virtual_agent_profile.system_prompt:
                        print(f"AGENT_PROFILE: ¡Éxito! Usando prompt del perfil dinámico '{virtual_agent_profile.name}'.")
                        docs_qa_template = virtual_agent_profile.system_prompt
                    else:
                        print("AGENT_PROFILE: No se encontró perfil de agente válido. Usando prompt por defecto de config.py.")
                    
                    # ===== Construcción de la cadena RAG con los prompts seleccionados =====
                    rag_memory = ConversationBufferWindowMemory(memory_key="chat_history", chat_memory=chat_message_history_for_chain, return_messages=True, k=CHAT_HISTORY_WINDOW_SIZE_RAG, output_key='answer')
                    vector_store_sync = get_chat_vector_store_sync()
                    retriever = vector_store_sync.as_retriever(search_kwargs={"k": MAX_RETRIEVED_CHUNKS_RAG, "filter": {"context_name": {"$in": final_rag_target_context_names}}})
                    
                    q_gen_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template(condense_template))
                    combine_docs_chain = load_qa_chain(llm=llm, chain_type="stuff", prompt=ChatPromptTemplate.from_template(docs_qa_template))
                    
                    conversational_rag_chain = ConversationalRetrievalChain(
                        retriever=retriever, question_generator=q_gen_chain, combine_docs_chain=combine_docs_chain,
                        memory=rag_memory, return_source_documents=True, verbose=LANGCHAIN_VERBOSE_FLAG
                    )
                    
                    rag_result = await asyncio.to_thread(conversational_rag_chain.invoke, {"question": question})
                    log_entry_data["bot_response"] = rag_result.get("answer", "[RAG Sin Respuesta]")
                    
                    retrieved_docs: List[LangchainDocument] = rag_result.get("source_documents", [])
                    if retrieved_docs:
                        summary_parts = []
                        detailed_sources = []
                        for idx, doc in enumerate(retrieved_docs):
                            meta = doc.metadata or {}
                            summary_parts.append(f"Doc{idx+1}:ctx='{meta.get('context_name', 'N/A')}',src='{meta.get('source_filename', 'N/A')}'")
                            s_detail = {"type": "DOCUMENT_CHUNK", "context_name": meta.get('context_name', 'N/A'), "source_identifier": meta.get('source_filename', 'N/A')}
                            detailed_sources.append(s_detail)
                        log_entry_data["retrieved_context_summary"] = "\n".join(summary_parts)
                        log_entry_data["metadata_details_json"]["used_sources"] = detailed_sources
                    # ===============================================
                    # ============ FIN RAMA RAG =====================
                    # ===============================================
    except Exception as e_uncaught:
        print(f"CHAT_EP_CRITICAL_ERROR: Excepción: {type(e_uncaught).__name__} - {e_uncaught}")
        traceback.print_exc()
        log_entry_data["error_message"] = f"Error Interno: {type(e_uncaught).__name__}"
        log_entry_data["bot_response"] = "[Chatbot tuvo un problema técnico.]"
    
    finally:
        # AQUÍ EMPIEZA TU BLOQUE FINALLY ORIGINAL, SIN CAMBIOS.
        ai_message_metadata_for_history_storage: Dict[str, Any] = {}
        intent_final = log_entry_data.get("intent", "UNKNOWN")
        
        if intent_final == "SQL_QUERY_DW":
            if context_def_dw_instance_orm: ai_message_metadata_for_history_storage["source_contexts_names"] = context_def_dw_instance_orm.name
            else: ai_message_metadata_for_history_storage["source_contexts_names"] = DW_CONTEXT_CONFIG_NAME
        elif intent_final == "RAG_DOCS_OR_SCHEMA":
            if final_rag_target_context_names: ai_message_metadata_for_history_storage["source_contexts_names"] = ", ".join(sorted(list(set(final_rag_target_context_names))))
            else: ai_message_metadata_for_history_storage["source_contexts_names"] = "NONE_RAG"
        elif "HUMAN_HANDOFF" in intent_final:
            handoff_details = log_entry_data.get("metadata_details_json", {}).get("handoff_info", {})
            if handoff_details:
                ai_message_metadata_for_history_storage["handoff_trigger_reason"] = intent_final 
                ai_message_metadata_for_history_storage["handoff_group"] = handoff_details.get("group_id")
        
        error_message = log_entry_data.get("error_message")
        bot_response = log_entry_data.get("bot_response", "")

        if not error_message:
            try:
                messages_to_add = [HumanMessage(content=question), AIMessage(content=bot_response, additional_kwargs=ai_message_metadata_for_history_storage)]
                history_writer = FullyCustomChatMessageHistory(session_id=user_dni_session_id)
                await asyncio.to_thread(history_writer.add_messages, messages_to_add)
            except Exception as e_hist_save:
                print(f"CHAT_EP_ERROR (Finally): Falló guardado final del historial: {e_hist_save}")

        end_time = time.time()
        log_entry_data["response_time_ms"] = int((end_time - start_time) * 1000)
        
        try:
            # Pasa directamente el diccionario. Tu CRUD se encargará de mapear los campos.
            await crud_interaction_log.create_interaction_log(db_crud, log_entry_data)
        except Exception as e_log_save:
            print(f"CHAT_EP_CRITICAL_ERROR (Finally): Falló guardado log de interacción: {e_log_save}")

    return ChatResponse(
        dni=chat_request.dni,
        original_message=question,
        bot_response=log_entry_data.get("bot_response", "").strip(),
        metadata_details_json=log_entry_data.get("metadata_details_json") 
    )

print("CHAT_EP_DEBUG: chat_api_endpoints.py module FULLY loaded.")