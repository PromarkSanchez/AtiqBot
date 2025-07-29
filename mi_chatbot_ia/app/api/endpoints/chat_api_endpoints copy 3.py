# app/api/endpoints/chat_api_endpoints.py
import os
import time
import traceback
from typing import List, Optional, Dict, Any, Union, Type, Set
import asyncio
import json
import httpx 

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
from app.models.human_agent import HumanAgent, HumanAgentGroup
from app.schemas.schemas import ChatRequest, ChatResponse
from app.crud import crud_interaction_log, crud_context_definition, crud_human_agent
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
GENERIC_NO_ANSWER_PHRASES = ["no tengo información", "no sé", "no pude encontrar", "no se encontraron contextos", "datos no disponibles", "disculpa, no encuentro eso"]

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

@router.post("/", response_model=ChatResponse)
async def process_chat_message_langchain(
    chat_request: ChatRequest,
    db_crud: AsyncSession = Depends(get_crud_db_session),
    current_api_client: ApiClientModel = Depends(get_validated_api_client)
):
    start_time = time.time(); question = chat_request.message; user_dni_session_id = chat_request.dni
    log_entry_data: Dict[str, Any] = { "user_dni": user_dni_session_id, "api_client_name": current_api_client.name, "user_message": question, "llm_model_used": ACTIVE_LLM_MODEL_NAME, "bot_response": "[Respuesta no generada por error]", "intent": "UNKNOWN", "metadata_details_json": {"used_sources": []}}
    print(f"CHAT_EP_INFO: Solicitud Chat: Cliente='{current_api_client.name}', UserID='{user_dni_session_id}', Pregunta='{question[:100]}...'")
    
    # Variables que pueden ser necesarias en `finally`
    context_def_dw_instance_orm: Optional[ContextDefinition] = None
    final_rag_target_context_names: List[str] = [] 
    api_client_settings = current_api_client.settings or {} # Para handoff_group_id
    
    unfiltered_chat_history: FullyCustomChatMessageHistory
    chat_message_history_for_chain: ContextAwareFilteredHistory

    try:
        allowed_context_ids_from_client: List[int] = api_client_settings.get("allowed_context_ids", [])
        resolved_api_client_allowed_context_names: List[str] = []
        if allowed_context_ids_from_client:
            stmt_names = select(ContextDefinition.name).filter(ContextDefinition.id.in_(allowed_context_ids_from_client), ContextDefinition.is_active == True)
            result_names = await db_crud.execute(stmt_names); resolved_api_client_allowed_context_names = result_names.scalars().all()
        print(f"CHAT_EP_INFO (pre-historial): Contextos permitidos para ApiClient: {resolved_api_client_allowed_context_names or 'NINGUNO'}")

        unfiltered_chat_history = FullyCustomChatMessageHistory(session_id=user_dni_session_id)
        chat_message_history_for_chain = ContextAwareFilteredHistory(unfiltered_chat_history, resolved_api_client_allowed_context_names)
        
        if LANGCHAIN_VERBOSE_FLAG: # Log historial filtrado (opcional)
            try: await asyncio.to_thread(lambda: list(chat_message_history_for_chain.messages))
            except Exception as e: print(f"CHAT_EP_WARNING: Error cargando hist. filtrado (verbose): {e}")

        llm = get_langchain_llm()
        question_lower = question.lower()
        
        force_handoff_by_keyword = any(k in question_lower for k in HANDOFF_KEYWORDS)
        target_handoff_group_id_cfg = api_client_settings.get("human_handoff_agent_group_id")
        # Añadir prints de debug aquí para estas dos variables
        print(f"HANDOFF_DEBUG: force_handoff_by_keyword = {force_handoff_by_keyword} (basado en '{question_lower}')")
        print(f"HANDOFF_DEBUG: target_handoff_group_id_cfg del ApiClient = {target_handoff_group_id_cfg}")

        
        
        if force_handoff_by_keyword and target_handoff_group_id_cfg: # LOGICA DE HANDOFF POR KEYWORD
            print(f"CHAT_EP_INFO: Handoff FORZADO por keyword. Grupo ID {target_handoff_group_id_cfg}")
            print(f"CHAT_EP_INFO: Handoff FORZADO por keyword detectada. Grupo ID configurado: {target_handoff_group_id_cfg}")

            log_entry_data["intent"] = "HUMAN_HANDOFF_KEYWORD"
            hist_msgs_summary = await asyncio.to_thread(lambda: list(chat_message_history_for_chain.messages[-6:])) # Últimos 3 turnos
            summary = f"Usuario '{user_dni_session_id}' solicita derivación. Pregunta: '{question}'.\nHistorial: " + "\n".join([f"- {m.type}: {m.content}" for m in hist_msgs_summary])
            
            selected_agent = await select_human_agent_for_handoff(db_crud, target_handoff_group_id_cfg)
            if selected_agent and selected_agent.teams_id:
                # await notify_agent_via_teams(selected_agent.teams_id, summary)
                log_entry_data["bot_response"] = f"Entendido. Te contactaré con {selected_agent.full_name}. Por favor, espera."
                log_entry_data["metadata_details_json"]["handoff_info"] = {"type":"TEAMS_AGENT", "agent_name":selected_agent.full_name, "group_id":target_handoff_group_id_cfg}
            else:
                group = await crud_human_agent.get_human_agent_group_by_id(db_crud, group_id=target_handoff_group_id_cfg)
                ticket_id = await create_ticket_for_handoff(group.name if group else f"Grupo ID {target_handoff_group_id_cfg}", summary)
                log_entry_data["bot_response"] = f"Entendido. He creado un ticket ({ticket_id}) para que un especialista te contacte."
                log_entry_data["metadata_details_json"]["handoff_info"] = {"type":"TICKET", "group_id":target_handoff_group_id_cfg, "ticket_id":ticket_id}
        else: # FLUJO NORMAL: SQL o RAG
            print(f"CHAT_EP_INFO: NO se activó Handoff por keyword. Procediendo a SQL/RAG.")
            if not force_handoff_by_keyword:
                 print(f"  Razón: No se detectó keyword de handoff en la pregunta.")
            if not target_handoff_group_id_cfg:
                 print(f"  Razón: ApiClient no tiene configurado un human_handoff_agent_group_id.")
            is_sql_intent_heuristic = any(k in question_lower for k in SQL_INTENT_KEYWORDS) or any(p.lower() in question_lower for p in DW_TABLE_PREFIXES_FOR_INTENT)
            is_dw_context_allowed = DW_CONTEXT_CONFIG_NAME in resolved_api_client_allowed_context_names
            attempt_sql_query_flag = is_dw_context_allowed and is_sql_intent_heuristic
            print(f"CHAT_EP_DEBUG_ROUTE: IntenciónSQL? {is_sql_intent_heuristic} | DWPermitido? {is_dw_context_allowed} | IntentarSQL? {attempt_sql_query_flag}")

            if is_dw_context_allowed: # Solo cargar si está permitido
                 context_def_dw_instance_orm = await crud_context_definition.get_context_definition_by_name(db_crud, name=DW_CONTEXT_CONFIG_NAME, load_relations_fully=True)
                 # (Tus prints de debug para el contexto DW cargado)

            if attempt_sql_query_flag and context_def_dw_instance_orm and context_def_dw_instance_orm.is_active and \
               context_def_dw_instance_orm.main_type == ContextMainType.DATABASE_QUERY and context_def_dw_instance_orm.db_connection_config_id:
                print(f"CHAT_EP_INFO: ===== ENTRANDO A RAMA TEXT-TO-SQL ====="); log_entry_data["intent"] = "SQL_QUERY_DW"
                db_conn_orm: Optional[DatabaseConnectionConfig] = get_db_connection_by_id_sync(context_def_dw_instance_orm.db_connection_config_id)
                if not db_conn_orm: raise ValueError(f"Config BD ID '{context_def_dw_instance_orm.db_connection_config_id}' para DW no encontrada.")
                sql_policy_from_cfg = (context_def_dw_instance_orm.processing_config or {}).get("sql_select_policy", {})
                if not sql_policy_from_cfg or not sql_policy_from_cfg.get("allowed_tables_for_select"):
                     log_entry_data["bot_response"] = "Config SQL Policy incompleta."; log_entry_data["error_message"] = "SQL Policy: Falta/vacío 'allowed_tables_for_select'."; print(f"CHAT_EP_ERROR_SQL_POLICY: {log_entry_data['error_message']}")
                else:
                    sql_hist_str = ""; # TODO: Implementar historial para SQL si CHAT_HISTORY_WINDOW_SIZE_SQL > 0
                    sql_output = await run_text_to_sql_lcel_chain(question=question, chat_history_str=sql_hist_str, db_conn_config_for_sql=db_conn_orm, llm=llm, sql_policy=sql_policy_from_cfg)
                    log_entry_data["bot_response"] = sql_output["final_answer_llm"]
                    # --- METADATA PARA SQL ---
                    log_entry_data["metadata_details_json"]["used_sources"].append({"type": "DATABASE_QUERY_RESULT", "context_name": context_def_dw_instance_orm.name, "source_identifier": "Direct_SQL_Execution", "details": {"generated_sql": sql_output.get('generated_sql'), "dw_connection_used": db_conn_orm.name }})
                    log_entry_data["retrieved_context_summary"] = f"SQL: {str(sql_output.get('generated_sql'))[:70]}..."
            else: # ---- Rama RAG ----
                print(f"CHAT_EP_INFO: ===== ENTRANDO A RAMA RAG ====="); # (tus prints de razón RAG)
                log_entry_data["intent"] = "RAG_DOCS_OR_SCHEMA"
                primary_context_for_rag_prompts_orm: Optional[ContextDefinition] = None
                # final_rag_target_context_names ya fue inicializada arriba
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
                        summary_no_ctx = f"Usuario '{user_dni_session_id}' necesita ayuda con: '{question}', pero no se encontraron contextos RAG."
                        # (Aquí llamarías a la lógica de notificación con selected_agent o create_ticket)
                        log_entry_data["bot_response"] = DEFAULT_HANDOFF_MESSAGE_TO_USER + f" (Referencia: Grupo {target_handoff_group_id_cfg})"
                else:
                    rag_memory = ConversationBufferWindowMemory(memory_key="chat_history", chat_memory=chat_message_history_for_chain, return_messages=True, k=CHAT_HISTORY_WINDOW_SIZE_RAG, output_key='answer')
                    vector_store_sync = get_chat_vector_store_sync()
                    rag_metadata_filter = {"context_name": {"$in": final_rag_target_context_names}}
                    retriever = vector_store_sync.as_retriever(search_kwargs={"k": MAX_RETRIEVED_CHUNKS_RAG, "filter": rag_metadata_filter})
                    condense_template_str = settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE; docs_qa_template_str = settings.DEFAULT_RAG_DOCS_QA_TEMPLATE
                    if primary_context_for_rag_prompts_orm and primary_context_for_rag_prompts_orm.processing_config:
                        proc_cfg = primary_context_for_rag_prompts_orm.processing_config
                        rag_prompts_from_cfg = proc_cfg.get("rag_prompts"); 
                        if isinstance(rag_prompts_from_cfg, dict):
                            condense_template_str = rag_prompts_from_cfg.get("condense_question_template", condense_template_str)
                            docs_qa_template_str = rag_prompts_from_cfg.get("docs_qa_template", docs_qa_template_str)
                            print(f"CHAT_EP_INFO: Prompts RAG cargados de '{primary_context_for_rag_prompts_orm.name}'.")
                    q_gen_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template(condense_template_str), verbose=LANGCHAIN_VERBOSE_FLAG)
                    combine_docs_chain = load_qa_chain(llm=llm, chain_type="stuff", prompt=ChatPromptTemplate.from_template(docs_qa_template_str), verbose=LANGCHAIN_VERBOSE_FLAG)
                    conversational_rag_chain = ConversationalRetrievalChain(retriever=retriever, question_generator=q_gen_chain, combine_docs_chain=combine_docs_chain, memory=rag_memory, return_source_documents=True, verbose=LANGCHAIN_VERBOSE_FLAG)
                    print(f"CHAT_EP_INFO: Invocando RAG para Sesión: '{user_dni_session_id}'...")
                    rag_result = await asyncio.to_thread(conversational_rag_chain.invoke, {"question": question})
                    bot_response_from_rag = rag_result.get("answer", "[RAG Sin Respuesta]")
                    log_entry_data["bot_response"] = bot_response_from_rag
                    
                    retrieved_docs: List[LangchainDocument] = rag_result.get("source_documents", [])
                    print(f"CHAT_EP_DEBUG_RAG: Documentos recuperados por retriever: {len(retrieved_docs)}")
                    if retrieved_docs: # --- METADATA PARA RAG (COMO LA TENÍAS) ---
                        summary_parts = []; detailed_sources = []
                        for idx, doc in enumerate(retrieved_docs):
                            meta = doc.metadata or {}; summary_parts.append(f"Doc{idx+1}:ctx='{meta.get('context_name', 'N/A')}',src='{meta.get('source_filename') or meta.get('table_name_source','N/A')}'")
                            s_detail = {"type": "DOCUMENT_CHUNK", "context_name": meta.get('context_name', 'N/A'), "source_identifier": meta.get('source_filename') or (f"{meta.get('schema_name_source', '')}.{meta.get('table_name_source', 'N/A')}" if meta.get('table_name_source') else 'Desconocido'), "details": {"page_number": meta.get('source_page_number'), "retrieval_score": meta.get('score', meta.get('_score')), "chunk_preview": doc.page_content[:150] + "..." if doc.page_content else ""}}
                            s_detail["details"] = {k: v for k, v in s_detail["details"].items() if v is not None}; 
                            if not s_detail["details"]: del s_detail["details"]
                            detailed_sources.append(s_detail)
                        log_entry_data["retrieved_context_summary"] = "\n".join(summary_parts)
                        log_entry_data["metadata_details_json"]["used_sources"] = detailed_sources
                    else: log_entry_data["retrieved_context_summary"] = "RAG: No se recuperaron docs relevantes."

                    if target_handoff_group_id_cfg and any(phrase in bot_response_from_rag.lower() for phrase in GENERIC_NO_ANSWER_PHRASES):
                        log_entry_data["intent"] = "HUMAN_HANDOFF_RAG_NO_ANSWER"
                        # ... (Tu lógica de notificación y cambio de bot_response) ...
                        print(f"HANDOFF_TRIGGER (RAG no sabe): Grupo {target_handoff_group_id_cfg}"); log_entry_data["bot_response"] = DEFAULT_HANDOFF_MESSAGE_TO_USER 
    
    except Exception as e_uncaught: # ... (Tu manejo de excepciones)
        print(f"CHAT_EP_CRITICAL_ERROR: Excepción: {type(e_uncaught).__name__} - {e_uncaught}"); traceback.print_exc()
        log_entry_data["error_message"] = f"Error Interno: {type(e_uncaught).__name__}"; log_entry_data["bot_response"] = "[Chatbot tuvo problema técnico.]"
    finally:
        # Preparar metadatos para el historial de AIMessage
        ai_message_metadata_for_history_storage: Dict[str, Any] = {}
        intent_final = log_entry_data.get("intent", "UNKNOWN")
        
        if intent_final == "SQL_QUERY_DW":
            if context_def_dw_instance_orm: 
                ai_message_metadata_for_history_storage["source_contexts_names"] = context_def_dw_instance_orm.name
            else: # Fallback si context_def_dw_instance_orm no se cargó (raro si el intent es SQL)
                ai_message_metadata_for_history_storage["source_contexts_names"] = DW_CONTEXT_CONFIG_NAME
        elif intent_final == "RAG_DOCS_OR_SCHEMA":
            # final_rag_target_context_names debería estar definida si se entró a la rama RAG y se usaron contextos.
            # Si está vacía, significa que no se usaron contextos RAG o no se determinaron.
            if final_rag_target_context_names: 
                ai_message_metadata_for_history_storage["source_contexts_names"] = ", ".join(sorted(list(set(final_rag_target_context_names))))
            else: # Si RAG no usó contextos (ej. "No se encontraron contextos documentales...")
                ai_message_metadata_for_history_storage["source_contexts_names"] = "NONE_RAG" # O algún indicador
        elif "HUMAN_HANDOFF" in intent_final:
            # Los detalles del handoff ya deberían estar en log_entry_data["metadata_details_json"]["handoff_info"]
            # Si quieres duplicarlos o añadir algo específico para additional_kwargs del historial:
            handoff_details_for_hist = log_entry_data.get("metadata_details_json", {}).get("handoff_info", {})
            if handoff_details_for_hist:
                ai_message_metadata_for_history_storage["handoff_trigger_reason"] = intent_final 
                ai_message_metadata_for_history_storage["handoff_group"] = handoff_details_for_hist.get("group_id")
                # No necesariamente necesitamos duplicar todo "handoff_info" aquí si ya está en metadata_details_json

        # ---- Guardado en Historial de Chat ----
        # Acceder a log_entry_data usando .get() para evitar KeyError
        error_message_from_log = log_entry_data.get("error_message")
        bot_response_from_log = log_entry_data.get("bot_response", "[Respuesta de bot no encontrada en log_entry]")

        if error_message_from_log is None and \
           "[Respuesta no generada por error]" not in bot_response_from_log and \
           "[Chatbot tuvo problema técnico" not in bot_response_from_log:
            try:
                print(f"CHAT_EP_DEBUG (Finally): Guardando en historial (FullyCustom). Metadata para AIMessage: {ai_message_metadata_for_history_storage}")
                messages_to_add_to_history = [
                    HumanMessage(content=question), 
                    AIMessage(content=bot_response_from_log, additional_kwargs=ai_message_metadata_for_history_storage)
                ]
                # Usar una nueva instancia para la operación de escritura para evitar conflictos de sesión
                history_writer = FullyCustomChatMessageHistory(session_id=user_dni_session_id)
                await asyncio.to_thread(history_writer.add_messages, messages_to_add_to_history)
                print(f"CHAT_EP_INFO (Finally): Interacción guardada en historial (FullyCustom).")
            except Exception as e_hist_save_final_block: 
                print(f"CHAT_EP_ERROR (Finally): Falló guardado final del historial: {type(e_hist_save_final_block).__name__} - {e_hist_save_final_block}")
                traceback.print_exc(limit=2) # Para un poco más de detalle en este error

        # ---- Cálculo de Tiempo y Guardado en Log de Interacción ----
        end_time = time.time()
        log_entry_data["response_time_ms"] = int((end_time - start_time) * 1000) # Esta clave se crea/actualiza aquí
        
        # Construir el payload para el log de interacción de forma segura
        # Asumiendo que crud_interaction_log espera estas claves EXACTAS.
        log_payload_to_db = {
            "user_dni": log_entry_data.get("user_dni"),
            "api_client_name": log_entry_data.get("api_client_name"),
            "user_message": log_entry_data.get("user_message"),
            "retrieved_context_summary": log_entry_data.get("retrieved_context_summary"),
            "full_prompt_to_llm": log_entry_data.get("full_prompt_to_llm"),
            "llm_model_used": log_entry_data.get("llm_model_used"),
            "bot_response": log_entry_data.get("bot_response"), # Ya lo obtuvimos como bot_response_from_log
            "response_time_ms": log_entry_data.get("response_time_ms"),
            "error_message": log_entry_data.get("error_message"), # Ahora error_message_from_log
            "intent": log_entry_data.get("intent", "UNKNOWN"), # Usar default si no está
            # La clave para los detalles en tu schema/modelo de InteractionLog.
            # En tu log, parece que era 'metadata_details', que mapeaba a metadata_details_json en ChatResponse.
            # Si tu modelo InteractionLog tiene una columna 'metadata_details' de tipo JSON:
            "metadata_details": log_entry_data.get("metadata_details_json") 
        }

        try:
            print(f"CHAT_EP_DEBUG: Guardando log de interacción. Intent: '{log_entry_data.get('intent', 'UNKNOWN')}'")
            await crud_interaction_log.create_interaction_log(db_crud, log_entry_data)

            print("CHAT_EP_INFO (Finally): Log de interacción guardado.")
        except Exception as e_log_save_final_block: 
            print(f"CHAT_EP_CRITICAL_ERROR (Finally): Falló guardado log de interacción: {type(e_log_save_final_block).__name__} - {e_log_save_final_block}")
            safe_log_data_preview = {k: (str(v)[:100] + '...' if isinstance(v, str) and len(v) > 100 else v) for k,v in log_payload_to_db.items()} # Usar el dict seguro
            print(f"CHAT_EP_CRITICAL_ERROR_DATA (Finally): Datos del log fallido (preview): {safe_log_data_preview}")
            traceback.print_exc(limit=2)
            
    return ChatResponse(
        dni=chat_request.dni,
        original_message=question,
        bot_response=log_entry_data.get("bot_response", "[Error al obtener respuesta]").strip(),
        # Asegurar que metadata_details_json toma del log_entry_data correcto
        metadata_details_json=log_entry_data.get("metadata_details_json") 
    )
# --- Endpoint Auxiliar ---
@router.get("/list-models", summary="Listar Modelos LLM (Gemini)", deprecated=False)
async def list_available_llm_models():
    if not GEMINI_API_KEY_ENV: raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="API Key no configurada.")
    models_info = []; 
    try:
        for m in genai.list_models(): 
            if 'generateContent' in m.supported_generation_methods: models_info.append({"name": m.name, "display_name": m.display_name})
        return models_info
    except Exception as e: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error listando: {str(e)}")

print("CHAT_EP_DEBUG: chat_api_endpoints.py module FULLY loaded.")