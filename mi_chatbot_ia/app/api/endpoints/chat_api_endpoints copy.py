# app/api/endpoints/chat_api_endpoints.py
import os
import time
import traceback
from typing import List, Optional, Dict, Any, Union, Type
import asyncio
import json

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
from app.schemas.schemas import ChatRequest, ChatResponse
from app.crud import crud_interaction_log, crud_context_definition
from app.crud.crud_db_connection import get_db_connection_by_id_sync
from app.config import settings
from app.tools.sql_tools import run_text_to_sql_lcel_chain
from app.security.api_key_auth import get_validated_api_client

print("CHAT_EP_DEBUG: chat_api_endpoints.py module loading...")

# --- Constantes del Módulo (Leídas directamente desde settings) ---
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

# --- Configuración de Gemini ---
load_dotenv()
GEMINI_API_KEY_ENV = settings.GEMINI_API_KEY
if not GEMINI_API_KEY_ENV: print("CHAT_EP_WARNING: GEMINI_API_KEY no encontrado.")
else:
    try: genai.configure(api_key=GEMINI_API_KEY_ENV); print("CHAT_EP_INFO: Google Generative AI (Gemini) configurado.")
    except Exception as e: print(f"CHAT_EP_ERROR: Configurando genai: {e}")

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

# --- Instancias Singleton (Lazy Initialization) ---
_llm_chat_instance: Optional[ChatGoogleGenerativeAI] = None
_vector_store_instance_sync: Optional[PGVector] = None
_lc_sbert_embeddings_instance: Optional[SentenceTransformerEmbeddings] = None
_sync_history_engine = None 
_SyncHistorySessionLocalFactory = None 

# --- Funciones de obtención para Singletons ---
def get_lc_sbert_embeddings() -> SentenceTransformerEmbeddings:
    global _lc_sbert_embeddings_instance
    if _lc_sbert_embeddings_instance is None:
        print(f"CHAT_EP_INFO: Creando SBERT Embeddings instance: {MODEL_NAME_SBERT_FOR_EMBEDDING}")
        _lc_sbert_embeddings_instance = SentenceTransformerEmbeddings(model_name=MODEL_NAME_SBERT_FOR_EMBEDDING)
    return _lc_sbert_embeddings_instance

def get_langchain_llm() -> ChatGoogleGenerativeAI:
    global _llm_chat_instance
    if _llm_chat_instance is None:
        print(f"CHAT_EP_INFO: Creando ChatGoogleGenerativeAI LLM instance: {ACTIVE_LLM_MODEL_NAME}")
        if not GEMINI_API_KEY_ENV: raise ValueError("GEMINI_API_KEY es requerido para instanciar el LLM.")
        _llm_chat_instance = ChatGoogleGenerativeAI(model=ACTIVE_LLM_MODEL_NAME, google_api_key=GEMINI_API_KEY_ENV, temperature=settings.DEFAULT_LLM_TEMPERATURE)
        print("CHAT_EP_INFO: ChatGoogleGenerativeAI LLM instance creada.")
    return _llm_chat_instance

def get_chat_vector_store_sync() -> PGVector:
    global _vector_store_instance_sync
    if _vector_store_instance_sync is None:
        print(f"CHAT_EP_INFO: Creando PGVector (síncrono) instance. Collection: '{PGVECTOR_CHAT_COLLECTION_NAME}'")
        lc_embeddings = get_lc_sbert_embeddings()
        sync_vector_db_url = settings.SYNC_DATABASE_VECTOR_URL
        if not sync_vector_db_url: raise ValueError("SYNC_DATABASE_VECTOR_URL no configurada para PGVector.")
        _vector_store_instance_sync = PGVector(connection=sync_vector_db_url, embeddings=lc_embeddings, collection_name=PGVECTOR_CHAT_COLLECTION_NAME, use_jsonb=True, async_mode=False, create_extension=False)
        print(f"CHAT_EP_INFO: PGVector (síncrono) instance creada para '{PGVECTOR_CHAT_COLLECTION_NAME}'.")
    return _vector_store_instance_sync

# --- Implementación Personalizada del Historial de Chat ---
_HistoryBase = declarative_base()

class _HistoryMessageORM(_HistoryBase):
    __tablename__ = CHAT_HISTORY_TABLE_NAME
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(255), nullable=False, index=True)
    message = Column(SQLA_JSON_TYPE, nullable=False) 
    # created_at = Column(DateTime(timezone=True), server_default=func.now()) # Descomentar si la columna existe/se añade

    def __repr__(self) -> str: return f"<HistoryMessageORM(id={self.id}, session_id='{self.session_id}')>"

def get_sync_history_session() -> Session:
    global _sync_history_engine, _SyncHistorySessionLocalFactory
    if _sync_history_engine is None:
        sync_db_url = settings.SYNC_DATABASE_CRUD_URL
        if not sync_db_url: raise ValueError("SYNC_DATABASE_CRUD_URL (síncrona) no configurada para historial.")
        _sync_history_engine = create_engine(sync_db_url, echo=False)
        _HistoryBase.metadata.create_all(_sync_history_engine) 
        _SyncHistorySessionLocalFactory = sessionmaker(autocommit=False, autoflush=False, bind=_sync_history_engine)
        print(f"CHAT_EP_INFO: Engine y SessionFactory SÍNCRONOS para historial (re)creados desde: {sync_db_url[:30]}...")
    if not _SyncHistorySessionLocalFactory: raise RuntimeError("SyncHistorySessionLocalFactory no inicializada.")
    return _SyncHistorySessionLocalFactory()

class FullyCustomChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, session_id: str):
        if not session_id: raise ValueError("session_id es requerido para el historial.")
        self.session_id = session_id
        print(f"FullyCustomChatMessageHistory: Instanciada para session_id '{self.session_id}'.")

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
                    try: message_dict = json.loads(orm_msg.message); converted_messages.extend(messages_from_dict([message_dict]))
                    except json.JSONDecodeError: print(f"HIST_ERROR: Mensaje (str) ID {orm_msg.id} no es JSON válido.")
                else: print(f"HIST_WARNING: Mensaje ID {orm_msg.id} tipo inesperado: {type(orm_msg.message)}")
            if LANGCHAIN_VERBOSE_FLAG: print(f"HIST_DEBUG: Recuperados {len(converted_messages)} mensajes para session '{self.session_id}'.")
            return converted_messages
        except Exception as e: print(f"HIST_ERROR (get messages for '{self.session_id}'): {e}"); db_session.rollback(); raise
        finally: db_session.close()

    def add_messages(self, messages: List[BaseMessage]) -> None:
        db_session: Session = get_sync_history_session()
        try:
            for message in messages:
                message_as_dict = message_to_dict(message)
                orm_entry = _HistoryMessageORM(session_id=self.session_id, message=message_as_dict)
                db_session.add(orm_entry)
            db_session.commit()
            if LANGCHAIN_VERBOSE_FLAG: print(f"HIST_DEBUG: Añadidos {len(messages)} mensajes para session '{self.session_id}'.")
        except Exception as e: print(f"HIST_ERROR (add messages for '{self.session_id}'): {e}"); db_session.rollback(); raise
        finally: db_session.close()

    def clear(self) -> None:
        db_session: Session = get_sync_history_session()
        try:
            stmt = _HistoryMessageORM.__table__.delete().where(_HistoryMessageORM.session_id == self.session_id)
            db_session.execute(stmt); db_session.commit()
            if LANGCHAIN_VERBOSE_FLAG: print(f"HIST_DEBUG: Historial limpiado para session '{self.session_id}'.")
        except Exception as e: print(f"HIST_ERROR (clear for '{self.session_id}'): {e}"); db_session.rollback(); raise
        finally: db_session.close()

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
    
    chat_message_history_for_request: FullyCustomChatMessageHistory
    try:
        chat_message_history_for_request = FullyCustomChatMessageHistory(session_id=user_dni_session_id)
    except Exception as e_hist_init:
        print(f"CHAT_EP_ERROR_FATAL: Fallo inicializando historial: {e_hist_init}"); traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error con servicio de historial.")

    if LANGCHAIN_VERBOSE_FLAG:
        try:
            loaded_messages_verbose = await asyncio.to_thread(lambda: list(chat_message_history_for_request.messages))
            print(f"CHAT_EP_DEBUG: Historial (verbose): {len(loaded_messages_verbose)} mensajes para '{user_dni_session_id}'.")
        except Exception as e_load_hist_verbose:
            print(f"CHAT_EP_WARNING: Error cargando historial (verbose): {type(e_load_hist_verbose).__name__} - {e_load_hist_verbose}")

    try:
        llm = get_langchain_llm()
        api_client_settings = current_api_client.settings or {}
        allowed_context_ids_from_client: List[int] = api_client_settings.get("allowed_context_ids", [])
        resolved_api_client_allowed_context_names: List[str] = []
        if allowed_context_ids_from_client:
            stmt = select(ContextDefinition.name).filter(ContextDefinition.id.in_(allowed_context_ids_from_client), ContextDefinition.is_active == True)
            result = await db_crud.execute(stmt); resolved_api_client_allowed_context_names = result.scalars().all()
        print(f"CHAT_EP_INFO: Nombres de contextos (activos, permitidos) para ApiClient: {resolved_api_client_allowed_context_names or 'NINGUNO'}")

        question_lower = question.lower() # Convertir una vez
        is_sql_intent_heuristic = any(k in question_lower for k in SQL_INTENT_KEYWORDS) or any(p.lower() in question_lower for p in DW_TABLE_PREFIXES_FOR_INTENT)
        
        print(f"CHAT_EP_DEBUG_ROUTE: Pregunta (lower): '{question_lower}'")
        print(f"CHAT_EP_DEBUG_ROUTE: Keywords SQL (settings): {SQL_INTENT_KEYWORDS}")
        print(f"CHAT_EP_DEBUG_ROUTE: Heurística de Intención SQL = {is_sql_intent_heuristic}")
        
        is_dw_context_allowed = DW_CONTEXT_CONFIG_NAME in resolved_api_client_allowed_context_names
        print(f"CHAT_EP_DEBUG_ROUTE: Contexto DW ('{DW_CONTEXT_CONFIG_NAME}') permitido? {is_dw_context_allowed}")
        
        attempt_sql_query_flag = is_dw_context_allowed and is_sql_intent_heuristic
        print(f"CHAT_EP_DEBUG_ROUTE: ¿Intentar query SQL (attempt_sql_query_flag)? {attempt_sql_query_flag}")
        
        context_def_dw_instance_orm: Optional[ContextDefinition] = None
        if is_dw_context_allowed: # Cargar instancia de DW solo si está permitido, independientemente de la intención SQL
             context_def_dw_instance_orm = await crud_context_definition.get_context_definition_by_name(db_crud, name=DW_CONTEXT_CONFIG_NAME, load_relations_fully=True)
             if context_def_dw_instance_orm:
                print(f"CHAT_EP_DEBUG_ROUTE: DW Context ('{context_def_dw_instance_orm.name}') Cargado:")
                print(f"  is_active: {context_def_dw_instance_orm.is_active}")
                print(f"  main_type: {context_def_dw_instance_orm.main_type} (Esperado: {ContextMainType.DATABASE_QUERY})")
                print(f"  db_connection_config_id: {context_def_dw_instance_orm.db_connection_config_id}")
                # processing_cfg_dw = context_def_dw_instance_orm.processing_config or {}
                # print(f"  processing_config SQL policy (preview): {str(processing_cfg_dw.get('sql_select_policy'))[:100]}...")
             else:
                print(f"CHAT_EP_WARNING_ROUTE: Contexto DW '{DW_CONTEXT_CONFIG_NAME}' permitido pero NO encontrado o INACTIVO en BD.")
        
        # ---- Rama Text-to-SQL ----
        if attempt_sql_query_flag and context_def_dw_instance_orm and \
           context_def_dw_instance_orm.is_active and \
           context_def_dw_instance_orm.main_type == ContextMainType.DATABASE_QUERY and \
           context_def_dw_instance_orm.db_connection_config_id:
            print(f"CHAT_EP_INFO: ===== ENTRANDO A RAMA TEXT-TO-SQL =====")
            log_entry_data["intent"] = "SQL_QUERY_DW"
            db_conn_orm: Optional[DatabaseConnectionConfig] = get_db_connection_by_id_sync(context_def_dw_instance_orm.db_connection_config_id)
            if not db_conn_orm: raise ValueError(f"Config BD ID '{context_def_dw_instance_orm.db_connection_config_id}' para DW no encontrada.")
            
            sql_policy_from_cfg = (context_def_dw_instance_orm.processing_config or {}).get("sql_select_policy", {})
            # run_text_to_sql_lcel_chain espera `allowed_tables_for_select` dentro de `sql_policy_from_cfg`
            if not sql_policy_from_cfg or \
               not isinstance(sql_policy_from_cfg.get("allowed_tables_for_select"), list) or \
               not sql_policy_from_cfg.get("allowed_tables_for_select"): # Una lista vacía también es 'falsy'
                 log_entry_data["bot_response"] = "La configuración para consultas SQL (política de tablas permitidas) está incompleta o vacía."
                 log_entry_data["error_message"] = "Política SQL: Falta 'allowed_tables_for_select' o está vacía en processing_config.sql_select_policy."
                 print(f"CHAT_EP_ERROR_SQL_POLICY: {log_entry_data['error_message']}")
                 print(f"CHAT_EP_DEBUG_SQL_POLICY: sql_policy_from_cfg contenido: {sql_policy_from_cfg}") # Print para ver qué tiene
            else:
                sql_chat_history_for_llm: str = ""
                if CHAT_HISTORY_WINDOW_SIZE_SQL > 0:
                    # (Tu lógica para formatear el historial para SQL)
                    pass # Implementar si es necesario
                sql_output = await run_text_to_sql_lcel_chain(question=question, chat_history_str=sql_chat_history_for_llm, db_conn_config_for_sql=db_conn_orm, llm=llm, sql_policy=sql_policy_from_cfg)
                log_entry_data["bot_response"] = sql_output["final_answer_llm"]
                log_entry_data["metadata_details_json"]["used_sources"].append({
                    "type": "DATABASE_QUERY_RESULT", "context_name": context_def_dw_instance_orm.name,
                    "source_identifier": "Direct_SQL_Execution",
                    "details": {"generated_sql": sql_output.get('generated_sql'), "dw_connection_used": db_conn_orm.name }})
                log_entry_data["retrieved_context_summary"] = f"Respuesta desde BD ({db_conn_orm.name}). SQL: {str(sql_output.get('generated_sql'))[:100]}..."
        
        # ---- Rama RAG Documental / Esquema ----
        else:
            print(f"CHAT_EP_INFO: ===== ENTRANDO A RAMA RAG (SQL NO CUMPLIÓ CONDICIONES Ó INTENTO SQL FUE FALSE) =====")
            # Prints de debug adicionales si no entró a SQL:
            if attempt_sql_query_flag: # Significa que intentó SQL pero alguna otra condición falló
                if not (context_def_dw_instance_orm and context_def_dw_instance_orm.is_active): print("  Razón RAG (Post-IntentoSQL): Contexto DW no cargado o inactivo.")
                elif context_def_dw_instance_orm.main_type != ContextMainType.DATABASE_QUERY: print(f"  Razón RAG (Post-IntentoSQL): MainType DW es '{context_def_dw_instance_orm.main_type}'.")
                elif not context_def_dw_instance_orm.db_connection_config_id: print("  Razón RAG (Post-IntentoSQL): DW no tiene db_connection_config_id.")

            log_entry_data["intent"] = "RAG_DOCS_OR_SCHEMA"
            final_rag_target_context_names: List[str] = []
            primary_context_for_rag_prompts_orm: Optional[ContextDefinition] = None
            for ctx_name in resolved_api_client_allowed_context_names:
                current_ctx_orm: Optional[ContextDefinition] = None
                if ctx_name == DW_CONTEXT_CONFIG_NAME and context_def_dw_instance_orm: current_ctx_orm = context_def_dw_instance_orm
                else: current_ctx_orm = await crud_context_definition.get_context_definition_by_name(db_crud, name=ctx_name, load_relations_fully=False)
                if not current_ctx_orm or not current_ctx_orm.is_active: print(f"CHAT_EP_DEBUG_RAG: Contexto '{ctx_name}' no válido para RAG. Omitiendo."); continue
                
                include_in_rag = False
                # Si es documental puro, se incluye
                if current_ctx_orm.main_type == ContextMainType.DOCUMENTAL: include_in_rag = True
                # Si es el contexto DW, Y NO se intentó SQL (porque la intención no era SQL o el DW no estaba configurado para ello),
                # Y es de tipo DATABASE_QUERY (para obtener su schema para RAG)
                elif current_ctx_orm.name == DW_CONTEXT_CONFIG_NAME and not attempt_sql_query_flag and current_ctx_orm.main_type == ContextMainType.DATABASE_QUERY:
                    include_in_rag = True
                
                if include_in_rag:
                    final_rag_target_context_names.append(ctx_name)
                    if not primary_context_for_rag_prompts_orm: primary_context_for_rag_prompts_orm = current_ctx_orm
            
            print(f"CHAT_EP_INFO: Contextos finales para RAG: {final_rag_target_context_names or 'NINGUNO'}")
            if not final_rag_target_context_names:
                log_entry_data["bot_response"] = "No se encontraron contextos documentales o de esquema válidos para tu consulta."
            else:
                rag_memory = ConversationBufferWindowMemory(memory_key="chat_history", chat_memory=chat_message_history_for_request, return_messages=True, k=CHAT_HISTORY_WINDOW_SIZE_RAG, output_key='answer')
                vector_store_sync = get_chat_vector_store_sync()
                rag_metadata_filter = {"context_name": {"$in": final_rag_target_context_names}}
                retriever = vector_store_sync.as_retriever(search_kwargs={"k": MAX_RETRIEVED_CHUNKS_RAG, "filter": rag_metadata_filter})
                print(f"CHAT_EP_DEBUG: Retriever RAG con filtro: {rag_metadata_filter}")
                
                condense_template_str = settings.DEFAULT_RAG_CONDENSE_QUESTION_TEMPLATE
                docs_qa_template_str = settings.DEFAULT_RAG_DOCS_QA_TEMPLATE
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
                
                print(f"CHAT_EP_INFO: Invocando cadena RAG para Sesión: '{user_dni_session_id}'...")
                rag_result = await asyncio.to_thread(conversational_rag_chain.invoke, {"question": question})
                log_entry_data["bot_response"] = rag_result.get("answer", "[Respuesta RAG no obtenida]")
                
                retrieved_docs: List[LangchainDocument] = rag_result.get("source_documents", [])
                print(f"CHAT_EP_DEBUG_RAG: Documentos recuperados por retriever: {len(retrieved_docs)}")
                if retrieved_docs: # Construir metadata_details si hay documentos
                    summary_parts = []
                    detailed_sources = []
                    for idx, doc in enumerate(retrieved_docs):
                        meta = doc.metadata or {}
                        summary_parts.append(f"Doc{idx+1}:ctx='{meta.get('context_name', 'N/A')}',src='{meta.get('source_filename') or meta.get('table_name_source','N/A')}'")
                        source_detail = {"type": "DOCUMENT_CHUNK", "context_name": meta.get('context_name', 'N/A'), "source_identifier": meta.get('source_filename') or (f"{meta.get('schema_name_source', '')}.{meta.get('table_name_source', 'N/A')}" if meta.get('table_name_source') else 'Desconocido'), "details": {"page_number": meta.get('source_page_number'), "retrieval_score": meta.get('score', meta.get('_score')), "chunk_preview": doc.page_content[:150] + "..." if doc.page_content else ""}}
                        source_detail["details"] = {k: v for k, v in source_detail["details"].items() if v is not None}
                        if not source_detail["details"]: del source_detail["details"]
                        detailed_sources.append(source_detail)
                    log_entry_data["retrieved_context_summary"] = "\n".join(summary_parts)
                    log_entry_data["metadata_details_json"]["used_sources"] = detailed_sources
                else: log_entry_data["retrieved_context_summary"] = "RAG: No se recuperaron documentos relevantes del vector store."

    # --- Manejo de Excepciones (igual que antes) ---
    except ValueError as ve: print(f"CHAT_EP_ERROR: ValueError en flujo: {ve}"); traceback.print_exc(limit=3); log_entry_data["error_message"] = f"Error Config/Flujo: {str(ve)}"; log_entry_data["bot_response"] = "[Problema de config]"
    except HTTPException as http_e: raise http_e 
    except Exception as e_uncaught: print(f"CHAT_EP_CRITICAL_ERROR: Excepción general: {type(e_uncaught).__name__} - {e_uncaught}"); traceback.print_exc(); log_entry_data["error_message"] = f"Error Interno: {type(e_uncaught).__name__}"; log_entry_data["bot_response"] = "[Chatbot tuvo problema técnico.]"
    # --- Bloque Finally para Guardado (igual que antes, con la corrección del history_writer) ---
    finally:
        history_writer_instance_for_saving: Optional[FullyCustomChatMessageHistory] = None
        if 'chat_message_history_for_request' in locals() and log_entry_data["error_message"] is None and \
           "[Respuesta no generada por error]" not in log_entry_data["bot_response"] and \
           "[Chatbot tuvo problema técnico" not in log_entry_data["bot_response"]:
            try:
                print(f"CHAT_EP_DEBUG: Guardando interacción en historial (FullyCustom) para '{user_dni_session_id}'...")
                messages_to_add_to_hist = [HumanMessage(content=question), AIMessage(content=log_entry_data["bot_response"])]
                history_writer_instance_for_saving = FullyCustomChatMessageHistory(session_id=user_dni_session_id)
                await asyncio.to_thread(history_writer_instance_for_saving.add_messages, messages_to_add_to_hist)
                print(f"CHAT_EP_INFO: Interacción guardada en historial (FullyCustom).")
            except Exception as e_hist_save_final: print(f"CHAT_EP_ERROR: Falló guardado final historial (FullyCustom): {e_hist_save_final}; {traceback.format_exc(limit=2)}")
        
        end_time = time.time(); log_entry_data["response_time_ms"] = int((end_time - start_time) * 1000)
        try:
            print(f"CHAT_EP_DEBUG: Guardando log de interacción. Intent: '{log_entry_data.get('intent', 'UNKNOWN')}'")
            await crud_interaction_log.create_interaction_log(db_crud, log_entry_data)
            print("CHAT_EP_INFO: Log de interacción guardado.")
        except Exception as e_log_save_final: print(f"CHAT_EP_CRITICAL_ERROR: Falló guardado log: {e_log_save_final}")
            
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