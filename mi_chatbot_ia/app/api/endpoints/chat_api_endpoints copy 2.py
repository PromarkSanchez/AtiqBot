# app/api/endpoints/chat_api_endpoints.py
import os
import time
import traceback
from typing import List, Optional, Dict, Any, Union, Type, Set
import asyncio
import json
import httpx # Para futuras llamadas HTTP (Teams, Freshservice)

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy import select, create_engine, Column, Integer, Text, DateTime, String, JSON as SQLA_JSON_TYPE
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
import google.generativeai as genai

# Langchain Imports
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, messages_from_dict, message_to_dict
from langchain_core.documents import Document as LangchainDocument
from langchain_postgres.vectorstores import PGVector
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain.memory import ConversationBufferWindowMemory
from langchain.chains import ConversationalRetrievalChain
from langchain.chains.llm import LLMChain
from langchain.chains.question_answering import load_qa_chain

# Application Specific Imports
from app.db.session import get_crud_db_session
from app.models.api_client import ApiClient as ApiClientModel
from app.models.context_definition import ContextDefinition, ContextMainType
from app.models.db_connection_config import DatabaseConnectionConfig
from app.models.human_agent import HumanAgent, HumanAgentGroup # Para handoff
from app.schemas.schemas import ChatRequest, ChatResponse
from app.crud import crud_interaction_log, crud_context_definition, crud_human_agent # Añadir crud_human_agent
from app.crud.crud_db_connection import get_db_connection_by_id_sync
from app.config import settings
from app.tools.sql_tools import run_text_to_sql_lcel_chain
from app.security.api_key_auth import get_validated_api_client

print("CHAT_EP_DEBUG: chat_api_endpoints.py module loading...")

# --- Constantes del Módulo ---
MODEL_NAME_SBERT_FOR_EMBEDDING = settings.MODEL_NAME_SBERT_FOR_EMBEDDING
PGVECTOR_CHAT_COLLECTION_NAME = settings.PGVECTOR_CHAT_COLLECTION_NAME
ACTIVE_LLM_MODEL_NAME = settings.DEFAULT_LLM_MODEL_NAME
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

# --- Configuración de Gemini ---
load_dotenv()
GEMINI_API_KEY_ENV = settings.GEMINI_API_KEY
if not GEMINI_API_KEY_ENV: print("CHAT_EP_WARNING: GEMINI_API_KEY no encontrado.")
else:
    try: genai.configure(api_key=GEMINI_API_KEY_ENV); print("CHAT_EP_INFO: Google Generative AI (Gemini) configurado.")
    except Exception as e: print(f"CHAT_EP_ERROR: Configurando genai: {e}")

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

# --- Instancias Singleton ---
_llm_chat_instance: Optional[ChatGoogleGenerativeAI] = None
_vector_store_instance_sync: Optional[PGVector] = None
_lc_sbert_embeddings_instance: Optional[SentenceTransformerEmbeddings] = None
_sync_history_engine = None 
_SyncHistorySessionLocalFactory = None 

# --- Funciones Singleton (sin cambios en su lógica interna) ---
def get_lc_sbert_embeddings() -> SentenceTransformerEmbeddings:
    global _lc_sbert_embeddings_instance
    if _lc_sbert_embeddings_instance is None:
        print(f"CHAT_EP_INFO: Creando SBERT Embeddings: {MODEL_NAME_SBERT_FOR_EMBEDDING}")
        _lc_sbert_embeddings_instance = SentenceTransformerEmbeddings(model_name=MODEL_NAME_SBERT_FOR_EMBEDDING)
    return _lc_sbert_embeddings_instance
def get_langchain_llm() -> ChatGoogleGenerativeAI:
    global _llm_chat_instance
    if _llm_chat_instance is None:
        print(f"CHAT_EP_INFO: Creando ChatGoogleGenerativeAI LLM: {ACTIVE_LLM_MODEL_NAME}")
        if not GEMINI_API_KEY_ENV: raise ValueError("GEMINI_API_KEY es requerido.")
        _llm_chat_instance = ChatGoogleGenerativeAI(model=ACTIVE_LLM_MODEL_NAME, google_api_key=GEMINI_API_KEY_ENV, temperature=settings.DEFAULT_LLM_TEMPERATURE)
        print("CHAT_EP_INFO: LLM instance creada.")
    return _llm_chat_instance
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

# --- Implementación del Historial de Chat ---
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
        self.session_id = session_id # <<--- CORRECCIÓN: Asegurar que se asigna
        # El print ya lo tenías y estaba bien:
        # print(f"FullyCustomChatMessageHistory: Instanciada para session_id '{self.session_id}'.")

    @property
    def messages(self) -> List[BaseMessage]:
        db_session: Session = get_sync_history_session()
        try:
            stmt = select(_HistoryMessageORM).where(_HistoryMessageORM.session_id == self.session_id).order_by(_HistoryMessageORM.id.asc())
            orm_messages = db_session.execute(stmt).scalars().all()
            converted_messages: List[BaseMessage] = []
            for orm_msg in orm_messages: # Esta lógica ya la tenías y debería funcionar bien con JSONB
                if isinstance(orm_msg.message, dict): converted_messages.extend(messages_from_dict([orm_msg.message]))
                elif isinstance(orm_msg.message, str): # Fallback por si acaso
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
            for message in messages:
                db_session.add(_HistoryMessageORM(session_id=self.session_id, message=message_to_dict(message)))
            db_session.commit()
            if LANGCHAIN_VERBOSE_FLAG: print(f"HIST_DEBUG (FullyCustom): Añadidos {len(messages)} mensajes para session '{self.session_id}'.")
        except Exception as e: print(f"HIST_ERROR (FullyCustom/add): {e}"); db_session.rollback(); raise
        finally: db_session.close()

    def clear(self) -> None: # ... (igual que antes)
        db_session: Session = get_sync_history_session()
        try:
            db_session.execute(_HistoryMessageORM.__table__.delete().where(_HistoryMessageORM.session_id == self.session_id)); db_session.commit()
        except Exception as e: print(f"HIST_ERROR (FullyCustom/clear): {e}"); db_session.rollback(); raise
        finally: db_session.close()

# --- Wrapper de Historial con Filtrado por Contexto (Estrategia 4) ---
class ContextAwareFilteredHistory(BaseChatMessageHistory):
    def __init__(self, underlying_history: FullyCustomChatMessageHistory, allowed_context_names_current: List[str]):
        self.underlying_history = underlying_history
        self.allowed_context_names_current_set = set(allowed_context_names_current)
        self.session_id = underlying_history.session_id # Ahora underlying_history SÍ tiene session_id
        print(f"ContextAwareFilteredHistory: Instanciada. Wraps session '{self.session_id}'. Contextos actuales PERMITIDOS: {self.allowed_context_names_current_set}")

    @property
    def messages(self) -> List[BaseMessage]:
        all_messages = self.underlying_history.messages
        filtered_messages: List[BaseMessage] = []; idx = 0
        while idx < len(all_messages): # Lógica de filtrado como la definimos
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

# --- Placeholders para Notificación de Handoff ---
async def select_human_agent_for_handoff(db_for_crud: AsyncSession, group_id: int) -> Optional[HumanAgent]: # ... (tu código igual)
    group = await crud_human_agent.get_human_agent_group_by_id(db_for_crud, group_id=group_id, load_agents=True)
    if group and group.agents:
        for agent in group.agents:
            if agent.is_active and agent.teams_id: return agent
    return None
async def notify_agent_via_teams(agent_teams_id: str, summary_for_agent: str) -> Optional[str]:
    print(f"HANDOFF_TEAMS (SIMULACIÓN): Notificando agent_teams_id '{agent_teams_id}'. Mensaje: {summary_for_agent[:100]}...")
    # Aquí lógica con MS Graph. Ejemplo de deep link:
    # encoded_summary = requests.utils.quote(summary_for_agent[:1500]) # Teams tiene límite de URL
    # teams_link = f"{TEAMS_DEEPLINK_BASE_USER}{agent_teams_id}&message={encoded_summary}"
    # return teams_link
    return None # Placeholder
async def create_ticket_for_handoff(group_name: str, summary_for_agent: str) -> str:
    print(f"HANDOFF_TICKET (SIMULACIÓN): Creando ticket para grupo '{group_name}'. Resumen: {summary_for_agent[:100]}...")
    return f"TICKET_SIM_{int(time.time())}"

# --- Endpoint Principal del Chat ---
@router.post("/", response_model=ChatResponse)
async def process_chat_message_langchain(
    chat_request: ChatRequest,
    db_crud: AsyncSession = Depends(get_crud_db_session),
    current_api_client: ApiClientModel = Depends(get_validated_api_client)
):
    start_time = time.time(); question = chat_request.message; user_dni_session_id = chat_request.dni
    log_entry_data: Dict[str, Any] = { "user_dni": user_dni_session_id, "api_client_name": current_api_client.name, "user_message": question, "llm_model_used": ACTIVE_LLM_MODEL_NAME, "bot_response": "[Respuesta no generada por error]", "intent": "UNKNOWN", "retrieved_context_summary": None, "full_prompt_to_llm": None, "error_message": None, "metadata_details_json": {"used_sources": []}}
    print(f"CHAT_EP_INFO: Solicitud Chat: Cliente='{current_api_client.name}', UserID='{user_dni_session_id}', Pregunta='{question[:100]}...'")
    
    context_def_dw_instance_orm: Optional[ContextDefinition] = None
    final_rag_target_context_names: List[str] = [] 
    unfiltered_chat_history: FullyCustomChatMessageHistory
    chat_message_history_for_chain: ContextAwareFilteredHistory

    try:
        api_client_settings = current_api_client.settings or {}
        allowed_context_ids_from_client: List[int] = api_client_settings.get("allowed_context_ids", [])
        resolved_api_client_allowed_context_names: List[str] = []
        if allowed_context_ids_from_client:
            stmt_names = select(ContextDefinition.name).filter(ContextDefinition.id.in_(allowed_context_ids_from_client), ContextDefinition.is_active == True)
            result_names = await db_crud.execute(stmt_names); resolved_api_client_allowed_context_names = result_names.scalars().all()
        print(f"CHAT_EP_INFO (pre-historial): Contextos permitidos para ApiClient: {resolved_api_client_allowed_context_names or 'NINGUNO'}")

        unfiltered_chat_history = FullyCustomChatMessageHistory(session_id=user_dni_session_id)
        chat_message_history_for_chain = ContextAwareFilteredHistory(unfiltered_chat_history, resolved_api_client_allowed_context_names)
    except Exception as e_init_fail:
        print(f"CHAT_EP_ERROR_FATAL: Fallo en inicialización crítica (ApiClient/Contextos/Historial): {e_init_fail}"); traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error al configurar el chat.")

    if LANGCHAIN_VERBOSE_FLAG: await asyncio.to_thread(lambda: list(chat_message_history_for_chain.messages))

    try:
        llm = get_langchain_llm()
        question_lower = question.lower()
        
        force_handoff_by_keyword = any(k in question_lower for k in HANDOFF_KEYWORDS)
        target_handoff_group_id_cfg = api_client_settings.get("human_handoff_agent_group_id")
        
        if force_handoff_by_keyword and target_handoff_group_id_cfg:
            print(f"CHAT_EP_INFO: Handoff FORZADO por keyword. Grupo ID {target_handoff_group_id_cfg}")
            log_entry_data["intent"] = "HUMAN_HANDOFF_KEYWORD"
            hist_msgs_for_summary = await asyncio.to_thread(lambda: list(chat_message_history_for_chain.messages))
            summary = f"User: {question}\nContexto Chat: {len(hist_msgs_for_summary)} mensajes previos." # Resumen simple
            
            selected_agent = await select_human_agent_for_handoff(db_crud, target_handoff_group_id_cfg)
            if selected_agent and selected_agent.teams_id:
                # teams_chat_link = await notify_agent_via_teams(selected_agent.teams_id, summary) # La notificación real es async
                log_entry_data["bot_response"] = f"Te estoy conectando con {selected_agent.full_name}. Por favor, espera."
                log_entry_data["metadata_details_json"]["handoff_info"] = {"group_id": target_handoff_group_id_cfg, "agent_name": selected_agent.full_name, "type": "TEAMS"}
            else:
                group = await crud_human_agent.get_human_agent_group_by_id(db_crud, group_id=target_handoff_group_id_cfg)
                group_name_for_ticket = group.name if group else f"Grupo ID {target_handoff_group_id_cfg}"
                ticket_id = await create_ticket_for_handoff(group_name_for_ticket, summary)
                log_entry_data["bot_response"] = f"He generado un ticket ({ticket_id}) para que un especialista te contacte a la brevedad."
                log_entry_data["metadata_details_json"]["handoff_info"] = {"group_id": target_handoff_group_id_cfg, "ticket_id": ticket_id, "type": "TICKET"}
        else:
            is_sql_intent_heuristic = any(k in question_lower for k in SQL_INTENT_KEYWORDS) or any(p.lower() in question_lower for p in DW_TABLE_PREFIXES_FOR_INTENT)
            is_dw_context_allowed = DW_CONTEXT_CONFIG_NAME in resolved_api_client_allowed_context_names
            attempt_sql_query_flag = is_dw_context_allowed and is_sql_intent_heuristic
            print(f"CHAT_EP_DEBUG_ROUTE: IntenciónSQL? {is_sql_intent_heuristic} | DWPermitido? {is_dw_context_allowed} | IntentarSQL? {attempt_sql_query_flag}")

            if is_dw_context_allowed and (not context_def_dw_instance_orm):
                 context_def_dw_instance_orm = await crud_context_definition.get_context_definition_by_name(db_crud, name=DW_CONTEXT_CONFIG_NAME, load_relations_fully=True)
                 # (tus prints de debug de contexto DW)

            if attempt_sql_query_flag and context_def_dw_instance_orm and context_def_dw_instance_orm.is_active and \
               context_def_dw_instance_orm.main_type == ContextMainType.DATABASE_QUERY and context_def_dw_instance_orm.db_connection_config_id:
                print(f"CHAT_EP_INFO: ===== ENTRANDO A RAMA TEXT-TO-SQL ====="); log_entry_data["intent"] = "SQL_QUERY_DW"
                db_conn_orm: Optional[DatabaseConnectionConfig] = get_db_connection_by_id_sync(context_def_dw_instance_orm.db_connection_config_id)
                if not db_conn_orm: raise ValueError(f"Config BD ID '{context_def_dw_instance_orm.db_connection_config_id}' para DW no encontrada.")
                sql_policy_from_cfg = (context_def_dw_instance_orm.processing_config or {}).get("sql_select_policy", {})
                if not sql_policy_from_cfg or not sql_policy_from_cfg.get("allowed_tables_for_select"):
                     log_entry_data["bot_response"] = "Config SQL Policy incompleta."; log_entry_data["error_message"] = "SQL Policy: Falta 'allowed_tables_for_select'."; print(f"CHAT_EP_ERROR_SQL_POLICY: {log_entry_data['error_message']}")
                else:
                    # ... (Tu lógica para `sql_chat_history_for_llm` usando `chat_message_history_for_chain`)
                    sql_output = await run_text_to_sql_lcel_chain(question=question, chat_history_str="", db_conn_config_for_sql=db_conn_orm, llm=llm, sql_policy=sql_policy_from_cfg)
                    log_entry_data["bot_response"] = sql_output["final_answer_llm"] # ... (tu loggeo de metadata)
            else: # ---- Rama RAG ----
                print(f"CHAT_EP_INFO: ===== ENTRANDO A RAMA RAG ====="); #... (tus prints de razón RAG)
                log_entry_data["intent"] = "RAG_DOCS_OR_SCHEMA"
                primary_context_for_rag_prompts_orm: Optional[ContextDefinition] = None
                for ctx_name in resolved_api_client_allowed_context_names: # Construir final_rag_target_context_names
                    current_ctx_orm: Optional[ContextDefinition] = None
                    if ctx_name == DW_CONTEXT_CONFIG_NAME and context_def_dw_instance_orm: current_ctx_orm = context_def_dw_instance_orm
                    else: current_ctx_orm = await crud_context_definition.get_context_definition_by_name(db_crud, name=ctx_name, load_relations_fully=False)
                    if not current_ctx_orm or not current_ctx_orm.is_active: continue
                    include_in_rag = False
                    if current_ctx_orm.main_type == ContextMainType.DOCUMENTAL: include_in_rag = True
                    elif current_ctx_orm.name == DW_CONTEXT_CONFIG_NAME and not attempt_sql_query_flag and current_ctx_orm.main_type == ContextMainType.DATABASE_QUERY: include_in_rag = True
                    if include_in_rag: final_rag_target_context_names.append(ctx_name)
                    if not primary_context_for_rag_prompts_orm and include_in_rag: primary_context_for_rag_prompts_orm = current_ctx_orm
                
                print(f"CHAT_EP_INFO: Contextos finales para RAG: {final_rag_target_context_names or 'NINGUNO'}")
                if not final_rag_target_context_names:
                    log_entry_data["bot_response"] = "No encontré contextos documentales para tu consulta."
                    if target_handoff_group_id_cfg: # Intentar handoff si no hay contextos RAG
                        log_entry_data["intent"] = "HUMAN_HANDOFF_NO_CONTEXTS"
                        # ... (Tu lógica de notificación y cambiar bot_response)
                else:
                    rag_memory = ConversationBufferWindowMemory(memory_key="chat_history", chat_memory=chat_message_history_for_chain, return_messages=True, k=CHAT_HISTORY_WINDOW_SIZE_RAG, output_key='answer')
                    # ... (el resto de tu cadena RAG como la tenías)
                    vector_store_sync = get_chat_vector_store_sync()
                    rag_metadata_filter = {"context_name": {"$in": final_rag_target_context_names}}
                    retriever = vector_store_sync.as_retriever(search_kwargs={"k": MAX_RETRIEVED_CHUNKS_RAG, "filter": rag_metadata_filter})
                    condense_template_str = settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE; docs_qa_template_str = settings.DEFAULT_RAG_DOCS_QA_TEMPLATE 
                    # (Lógica de carga de prompts de `primary_context_for_rag_prompts_orm`)
                    q_gen_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template(condense_template_str), verbose=LANGCHAIN_VERBOSE_FLAG)
                    combine_docs_chain = load_qa_chain(llm=llm, chain_type="stuff", prompt=ChatPromptTemplate.from_template(docs_qa_template_str), verbose=LANGCHAIN_VERBOSE_FLAG)
                    conversational_rag_chain = ConversationalRetrievalChain(
                        retriever=retriever, 
                        question_generator=q_gen_chain, 
                        combine_docs_chain=combine_docs_chain, 
                        memory=rag_memory, 
                        return_source_documents=True, 
                        verbose=LANGCHAIN_VERBOSE_FLAG)
                    print(f"CHAT_EP_INFO: Invocando RAG para Sesión: '{user_dni_session_id}'...")
                    rag_result = await asyncio.to_thread(conversational_rag_chain.invoke, {"question": question})
                    bot_response_from_rag = rag_result.get("answer", "[RAG Sin Respuesta]")
                    log_entry_data["bot_response"] = bot_response_from_rag
                    
                    # Handoff si RAG no sabe
                    if target_handoff_group_id_cfg and any(phrase in bot_response_from_rag.lower() for phrase in ["no tengo información", "no sé"]):
                        log_entry_data["intent"] = "HUMAN_HANDOFF_RAG_NO_ANSWER"; log_entry_data["bot_response"] = DEFAULT_HANDOFF_MESSAGE_TO_USER # ... (notificación)
                    else: # Poblar metadata_details
                        # ... (tu lógica de poblar metadata_details con retrieved_docs)
                        pass


    except Exception as e_uncaught: # ... (tu manejo de errores)
        print(f"CHAT_EP_CRITICAL_ERROR: Excepción: {type(e_uncaught).__name__} - {e_uncaught}"); traceback.print_exc()
        log_entry_data["error_message"] = f"Error Interno: {type(e_uncaught).__name__}"; log_entry_data["bot_response"] = "[Chatbot tuvo problema técnico.]"
    finally: # ... (tu finally, asegurando que `final_rag_target_context_names` y `context_def_dw_instance_orm` se usen para `source_contexts_names`)
        ai_message_metadata_for_history_storage: Dict[str, Any] = {}
        current_intent = log_entry_data.get("intent", "UNKNOWN")
        if current_intent == "SQL_QUERY_DW":
            if context_def_dw_instance_orm: ai_message_metadata_for_history_storage["source_contexts_names"] = context_def_dw_instance_orm.name
            else: ai_message_metadata_for_history_storage["source_contexts_names"] = DW_CONTEXT_CONFIG_NAME
        elif current_intent == "RAG_DOCS_OR_SCHEMA":
            if final_rag_target_context_names: ai_message_metadata_for_history_storage["source_contexts_names"] = ", ".join(sorted(list(set(final_rag_target_context_names))))
        elif "HUMAN_HANDOFF" in current_intent:
            ai_message_metadata_for_history_storage["handoff_details"] = log_entry_data.get("metadata_details_json",{}).get("handoff_info", {})
        
        if log_entry_data["error_message"] is None and "[Respuesta no generada por error]" not in log_entry_data["bot_response"]:
            try: # ... (tu guardado de historial)
                messages_to_add = [HumanMessage(content=question), AIMessage(content=log_entry_data["bot_response"], additional_kwargs=ai_message_metadata_for_history_storage)]
                # Usar el unfiltered_chat_history o una nueva instancia de FullyCustom para guardar. Es mejor una nueva para evitar problemas de sesión.
                hist_writer = FullyCustomChatMessageHistory(session_id=user_dni_session_id)
                await asyncio.to_thread(hist_writer.add_messages, messages_to_add)
            except Exception as e_hist_save: print(f"CHAT_EP_ERROR: Falló guardado historial: {e_hist_save}")

        end_time = time.time(); log_entry_data["response_time_ms"] = int((end_time - start_time) * 1000)
        try: await crud_interaction_log.create_interaction_log(db_crud, log_entry_data); print("CHAT_EP_INFO: Log guardado.")
        except Exception as e_log_save: print(f"CHAT_EP_CRITICAL_ERROR: Falló guardado log: {e_log_save}")
            
    return ChatResponse(dni=chat_request.dni,original_message=question,bot_response=log_entry_data["bot_response"].strip(), metadata_details_json=log_entry_data.get("metadata_details_json"))

 

# --- Endpoint Auxiliar (Listar Modelos) ---
@router.get("/list-models", summary="Listar Modelos LLM Disponibles (Gemini)", deprecated=True)
async def list_available_llm_models(): # Tu código igual...
    if not GEMINI_API_KEY_ENV: raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="API Key no configurada.")
    models_info = []; 
    try:
        for m in genai.list_models(): 
            if 'generateContent' in m.supported_generation_methods:
                models_info.append({"name": m.name, "version": m.version, "display_name": m.display_name,"description": m.description, "input_token_limit": m.input_token_limit,"output_token_limit": m.output_token_limit})
        return models_info
    except Exception as e: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error listando modelos: {str(e)}")

print("CHAT_EP_DEBUG: chat_api_endpoints.py module FULLY loaded.")