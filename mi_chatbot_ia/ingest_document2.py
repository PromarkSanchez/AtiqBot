# mi_chatbot_ia/ingest_document.py
import asyncio
import os
import json
from typing import List, Dict, Any, Optional, Tuple # Añadido Tuple

# Langchain imports
from langchain_core.documents import Document as LangchainCoreDocument # type: ignore
from langchain_community.document_loaders import TextLoader # type: ignore
try:
    from langchain_community.document_loaders import PyPDFLoader # type: ignore
except ImportError:
    PyPDFLoader = None # type: ignore
    print("ADVERTENCIA: PyPDFLoader no está disponible. La carga de PDFs fallará. Ejecuta: pip install pypdf")

from langchain_text_splitters import RecursiveCharacterTextSplitter # type: ignore
from langchain_postgres.vectorstores import PGVector # type: ignore
from langchain_community.embeddings import SentenceTransformerEmbeddings # type: ignore

# SQLAlchemy y modelos para leer configuraciones
from sqlalchemy.ext.asyncio import AsyncSession # type: ignore
from sqlalchemy.future import select # type: ignore
from sqlalchemy.orm import selectinload # type: ignore

import pyodbc # Para conectar a SQL Server # type: ignore

# Módulos de la aplicación
from app.db.session import AsyncSessionLocal_CRUD, async_engine_crud
from app.models.context_definition import ContextDefinition, ContextMainType
from app.models.document_source_config import DocumentSourceConfig, SupportedDocSourceType
from app.models.db_connection_config import DatabaseConnectionConfig, SupportedDBType # Para la config de conexión
from app.utils.security_utils import decrypt_data # Para desencriptar contraseñas de BD
from app.config import settings
import traceback

# --- Configuración Global del Script de Ingesta ---
MODEL_NAME_SBERT_FOR_EMBEDDING = 'all-MiniLM-L6-v2'
DIMENSION_SBERT_EMBEDDING = 384
# Este será el nombre de la colección principal en PGVector.
# Para una prueba limpia, puedes cambiarlo y poner pre_delete_collection=True abajo.
PGVECTOR_MAIN_COLLECTION_NAME = "chatbot_knowledge_base_v1" 
# -------------------------------------------------

_sbert_embeddings_instance: Optional[SentenceTransformerEmbeddings] = None

def get_sbert_embeddings_instance() -> SentenceTransformerEmbeddings:
    global _sbert_embeddings_instance
    if _sbert_embeddings_instance is None:
        print(f"Creando instancia global de SentenceTransformerEmbeddings: {MODEL_NAME_SBERT_FOR_EMBEDDING}")
        _sbert_embeddings_instance = SentenceTransformerEmbeddings(model_name=MODEL_NAME_SBERT_FOR_EMBEDDING)
    return _sbert_embeddings_instance

def fetch_data_from_db(db_conn_config: DatabaseConnectionConfig, query: str) -> List[Dict[str, Any]]:
    print(f"    Intentando conectar a: '{db_conn_config.name}' (Tipo: {db_conn_config.db_type.value})")
    password = ""
    if db_conn_config.encrypted_password:
        password = decrypt_data(db_conn_config.encrypted_password)
        if password == "[DATO ENCRIPTADO INVÁLIDO]":
            print(f"      ERROR DB_CONN: No se pudo desencriptar la contraseña para la conexión '{db_conn_config.name}'.")
            return []

    if db_conn_config.db_type == SupportedDBType.SQLSERVER:
        driver = "{ODBC Driver 17 for SQL Server}" # Default
        if db_conn_config.extra_params and "driver" in db_conn_config.extra_params:
            driver = db_conn_config.extra_params["driver"]
        
        conn_str = (
            f"DRIVER={driver};"  # No poner llaves extra alrededor de driver si ya las tiene
            f"SERVER={db_conn_config.host},{db_conn_config.port};"
            f"DATABASE={db_conn_config.database_name};"
            f"UID={db_conn_config.username};"
            f"PWD={password};"
        )
        if db_conn_config.extra_params:
            for k, v in db_conn_config.extra_params.items():
                if k.lower() != "driver": conn_str += f"{k}={v};"

        print(f"    Conectando a SQL Server con pyodbc: SERVER={db_conn_config.host} DB={db_conn_config.database_name}")
        results = []
        try:
            with pyodbc.connect(conn_str, timeout=15) as cnxn:
                with cnxn.cursor() as cursor:
                    cursor.execute(query)
                    columns = [column[0] for column in cursor.description]
                    for row_val in cursor.fetchall(): # Renombrada variable local 'row' a 'row_val'
                        results.append(dict(zip(columns, row_val)))
            print(f"    Query a SQL Server ejecutada, {len(results)} filas obtenidas.")
            return results
        except pyodbc.Error as ex:
            sqlstate = ex.args[0]
            print(f"    ERROR pyodbc al conectar/ejecutar query en '{db_conn_config.name}': {sqlstate} - {ex}")
            print(f"    Connection string intentada: {conn_str.replace(password, '********') if password else conn_str}")
            return []
        except Exception as e_gen:
            print(f"    ERROR GENERAL al conectar/ejecutar query en '{db_conn_config.name}': {e_gen}")
            return []
    else:
        print(f"    Tipo de BD '{db_conn_config.db_type.value}' aún no soportado para query directa en ingesta.")
        return []

async def process_document_source(
    doc_source: DocumentSourceConfig,
    context_def: ContextDefinition,
    vector_store: PGVector
):
    print(f"  Procesando Origen de Documento: '{doc_source.name}' (Tipo: {doc_source.source_type.value}) para Contexto '{context_def.name}'")
    if doc_source.source_type == SupportedDocSourceType.LOCAL_FOLDER:
        path_config = doc_source.path_or_config
        if not isinstance(path_config, dict) or "path" not in path_config:
            print(f"    ERROR: 'path_or_config' malformado para LOCAL_FOLDER (ID: {doc_source.id}).")
            return
        folder_path = path_config["path"]
        if not os.path.isdir(folder_path):
            print(f"    ERROR: Ruta para LOCAL_FOLDER '{folder_path}' no existe (Origen ID: {doc_source.id}).")
            return

        print(f"    Cargando documentos desde: {folder_path}")
        loaded_docs_for_source: List[LangchainCoreDocument] = []
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if not os.path.isfile(file_path): continue

            current_file_docs: List[LangchainCoreDocument] = []
            file_type_processed = None
            if filename.lower().endswith(('.txt', '.md')):
                print(f"      Intentando cargar archivo de texto/markdown: {filename}")
                try:
                    loader = TextLoader(file_path, encoding='utf-8')
                    current_file_docs = loader.load()
                    file_type_processed = "text"
                    print(f"        '{filename}' cargado ({len(current_file_docs)} doc(s) Langchain).")
                except Exception as e: print(f"      ERROR TEXTLOADER '{filename}': {e}")
            elif filename.lower().endswith('.pdf'):
                print(f"      Intentando cargar PDF: {filename}")
                if PyPDFLoader is None:
                    print("      ERROR: PyPDFLoader no disponible (pip install pypdf).")
                    continue
                try:
                    loader = PyPDFLoader(file_path)
                    current_file_docs = loader.load_and_split()
                    file_type_processed = "pdf"
                    print(f"        '{filename}' cargado como PDF ({len(current_file_docs)} página(s)).")
                except Exception as e_pdf:
                    if "invalid pdf header" in str(e_pdf).lower() or "eof marker" in str(e_pdf).lower():
                        print(f"      ADVERTENCIA: '{filename}' no es PDF válido o está corrupto. Omitiendo. ({e_pdf})")
                    else:
                        print(f"      ERROR PDFLOADER '{filename}': {e_pdf}"); traceback.print_exc()
            else: print(f"      Archivo '{filename}' omitido (tipo no soportado).")

            if file_type_processed and current_file_docs:
                for doc in current_file_docs:
                    doc.metadata = doc.metadata or {}
                    doc.metadata.update({
                        'source_filename': filename, 'source_doc_source_id': doc_source.id,
                        'source_doc_source_name': doc_source.name
                    })
                    if file_type_processed == "pdf" and 'page' in doc.metadata:
                         doc.metadata['source_page_number'] = doc.metadata['page'] + 1
                loaded_docs_for_source.extend(current_file_docs)
        
        if not loaded_docs_for_source:
            print(f"    No se cargaron documentos de '{doc_source.name}'.")
            return
        
        chunk_size = context_def.processing_config.get("chunk_size", 500) if context_def.processing_config else 500
        chunk_overlap = context_def.processing_config.get("chunk_overlap", 50) if context_def.processing_config else 50
        print(f"    Dividiendo {len(loaded_docs_for_source)} doc(s) en chunks (size:{chunk_size}, overlap:{chunk_overlap})...")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        split_chunks = text_splitter.split_documents(loaded_docs_for_source)
        print(f"    Total chunks para '{doc_source.name}': {len(split_chunks)}")
        if not split_chunks: print(f"    No se generaron chunks para '{doc_source.name}'."); return

        for i_chunk, chunk_lc_doc in enumerate(split_chunks):
            chunk_lc_doc.metadata = chunk_lc_doc.metadata or {}
            chunk_lc_doc.metadata.update({
                'context_id': context_def.id, 'context_name': str(context_def.name),
                'context_main_type': str(context_def.main_type.value)
            })
            if i_chunk < 2: print(f"      METADATA PARA CHUNK DOC {i_chunk+1}: {chunk_lc_doc.metadata}")

        print(f"    Ingestando {len(split_chunks)} chunks en PGVector '{vector_store.collection_name}'...")
        try:
            vector_store.add_documents(documents=split_chunks)
            print(f"    Chunks de '{doc_source.name}' para contexto '{context_def.name}' INGESTADOS.")
        except Exception as e: print(f"    ERROR al ingestar en PGVector: {e}"); traceback.print_exc()
    
    elif doc_source.source_type == SupportedDocSourceType.S3_BUCKET:
        print(f"    INFO: Ingesta S3_BUCKET (ID: {doc_source.id}) no implementada.")
    # ... (otros elif) ...

async def process_database_query_context(
    context_def: ContextDefinition,
    db_crud_session: AsyncSession, # Para cargar DBConnConfig
    vector_store: PGVector
):
    print(f"  Procesando Contexto DATABASE_QUERY: '{context_def.name}' (ID: {context_def.id})")
    if not context_def.processing_config or "dictionary_table_query" not in context_def.processing_config:
        print(f"    ERROR: Falta 'dictionary_table_query' en processing_config para Contexto '{context_def.name}'.")
        return
    dict_query = context_def.processing_config["dictionary_table_query"]
    if not context_def.db_connections:
        print(f"    ERROR: Contexto '{context_def.name}' no tiene db_connections asociadas.")
        return

    db_conn_proxy = context_def.db_connections[0] # Asumimos el primero de la lista
    db_conn_config_obj = await db_crud_session.get(DatabaseConnectionConfig, db_conn_proxy.id) # Usar get para cargar
    if not db_conn_config_obj:
        print(f"    ERROR: No se pudo cargar DBConnectionConfig (ID: {db_conn_proxy.id}) para Contexto '{context_def.name}'.")
        return

    print(f"    Usando DB Connection: '{db_conn_config_obj.name}'. Query: {dict_query[:100]}...")
    schema_rows = await asyncio.to_thread(fetch_data_from_db, db_conn_config_obj, dict_query)
    if schema_rows is None: print(f"    Fallo al ejecutar query para '{db_conn_config_obj.name}'."); return
    if not schema_rows: print(f"    No se obtuvieron datos del diccionario de '{db_conn_config_obj.name}'."); return
    print(f"    {len(schema_rows)} filas del diccionario de datos. Generando documentos de esquema...")

    tables_data: Dict[Tuple[str, str], Dict[str, Any]] = {}
    custom_table_descs = context_def.processing_config.get("custom_table_descriptions", {})
    default_table_desc = context_def.processing_config.get("table_description_template_default_desc", "N/A")
    col_template = context_def.processing_config.get("column_description_template", "- {columna} ({tipo}{longitud_str}) Nulos:{permite_nulos} AutoInc:{es_autonumerico} Desc:{descripcion_columna} {fk_info}")
    intro_template = context_def.processing_config.get("table_description_template_intro", "Tabla [{esquema}].[{tabla}]: {custom_table_desc_or_default}. Columnas:")

    for row in schema_rows:
        s_name, t_name, c_name = str(row.get("esquema","")).strip(), str(row.get("tabla","")).strip(), str(row.get("columna","")).strip()
        if not s_name or not t_name or not c_name: print(f"      ADVERTENCIA: Fila incompleta: {row}"); continue
        
        table_key = (s_name, t_name)
        if table_key not in tables_data:
            custom_desc_key = f"{s_name}.{t_name}"
            tables_data[table_key] = {"cols_info": [], "custom_desc": custom_table_descs.get(custom_desc_key, default_table_desc), "esquema": s_name}

        longitud = row.get("longitud"); tipo_col_l = str(row.get("tipo", "")).lower()
        l_str = ""
        if longitud is not None and tipo_col_l in ["varchar", "nvarchar", "char", "nchar", "text", "ntext", "varbinary", "character varying", "ncharacter varying"]:
            if isinstance(longitud, (int, float)) and longitud == -1: l_str = "(MAX)"
            elif isinstance(longitud, (int, float)) and longitud > 0: l_str = f"({int(longitud)})"
            elif isinstance(longitud, str) and longitud.strip(): l_str = f"({longitud.strip()})"
        
        fk_str = ""; fk_val = row.get("ForeignKey")
        is_fk = (isinstance(fk_val, str) and fk_val.upper() in ["SI", "S", "YES", "TRUE", "1"]) or \
                (isinstance(fk_val, bool) and fk_val) or \
                (isinstance(fk_val, int) and fk_val == 1)
        if is_fk: fk_str = f" Ref: [{row.get('ReferenceTableName','N/A')}].[{row.get('ReferenceColumnName','N/A')}]."
        
        col_info = col_template.format(esquema=s_name,tabla=t_name,columna=c_name,tipo=row.get("tipo","N/A"),longitud_str=l_str,
                                     permite_nulos=row.get("permite_nulos_vista","N/A"), es_autonumerico=row.get("es_autonumerico_vista","N/A"),
                                     descripcion_columna=row.get("descripcion","N/D"),fk_info=fk_str)
        tables_data[table_key]["cols_info"].append(col_info)

    schema_lc_docs: List[LangchainCoreDocument] = []
    for (s_name, t_name), data in tables_data.items():
        intro = intro_template.format(esquema=s_name, tabla=t_name, custom_table_desc_or_default=data["custom_desc"])
        cols_text = "\n".join(data["cols_info"])
        full_text = f"{intro}\n{cols_text}"
        meta = {"source_type": "DATABASE_SCHEMA_INFO", "db_connection_name": db_conn_config_obj.name,
                "db_name_source": db_conn_config_obj.database_name, "schema_name_source": s_name,
                "table_name_source": t_name, "source_doc_source_id": db_conn_config_obj.id,
                "source_doc_source_name": db_conn_config_obj.name}
        schema_lc_docs.append(LangchainCoreDocument(page_content=full_text, metadata=meta))
        print(f"    Doc esquema: [{s_name}].[{t_name}] ({len(full_text)} chars)")

    if not schema_lc_docs: print("    No se generaron docs de esquema."); return

    cs = context_def.processing_config.get("db_schema_chunk_size", 1500)
    co = context_def.processing_config.get("db_schema_chunk_overlap", 150)
    print(f"    Dividiendo {len(schema_lc_docs)} doc(s) de esquema en chunks (size:{cs}, overlap:{co})...")
    splitter = RecursiveCharacterTextSplitter(chunk_size=cs, chunk_overlap=co)
    schema_chunks = splitter.split_documents(schema_lc_docs)
    print(f"    Total chunks de esquema: {len(schema_chunks)}")
    if not schema_chunks: print("    No se generaron chunks de esquema."); return

    print(f"    Añadiendo metadatos Contexto '{context_def.name}' a chunks de esquema...")
    for i_chunk, chunk in enumerate(schema_chunks):
        chunk.metadata = chunk.metadata or {}
        chunk.metadata.update({'context_id': context_def.id, 'context_name': str(context_def.name),
                               'context_main_type': str(context_def.main_type.value)})
        if i_chunk < 2: print(f"      METADATA CHUNK ESQUEMA {i_chunk+1}: {chunk.metadata}")

    print(f"    Ingestando {len(schema_chunks)} chunks de esquema en PGVector '{vector_store.collection_name}'...")
    try:
        vector_store.add_documents(documents=schema_chunks)
        print(f"    Chunks de esquema del Contexto '{context_def.name}' INGESTADOS.")
    except Exception as e: print(f"    ERROR al ingestar chunks de esquema: {e}"); traceback.print_exc()

async def run_ingestion_pipeline():
    print(f"--- Iniciando Pipeline de Ingesta de Contextos (Colección: {PGVECTOR_MAIN_COLLECTION_NAME}) ---")
    embeddings_func = get_sbert_embeddings_instance()
    
    base_vec_url = str(settings.DATABASE_VECTOR_URL)
    sync_vec_url_for_pgvec: str
    if "postgresql+asyncpg://" in base_vec_url:
        sync_vec_url_for_pgvec = base_vec_url.replace("postgresql+asyncpg://", "postgresql://")
    elif "postgresql://" in base_vec_url:
        sync_vec_url_for_pgvec = base_vec_url
    else:
        print(f"ERROR: Formato DATABASE_VECTOR_URL no reconocido: {base_vec_url}")
        return
    print(f"Configurando VectorStore PGVector con URL SÍNCRONA: {sync_vec_url_for_pgvec} para '{PGVECTOR_MAIN_COLLECTION_NAME}'")
    
    main_vector_store: Optional[PGVector] = None
    try:
        main_vector_store = PGVector(
            connection=sync_vec_url_for_pgvec,
            embeddings=embeddings_func,
            collection_name=PGVECTOR_MAIN_COLLECTION_NAME,
            embedding_length=DIMENSION_SBERT_EMBEDDING,
            pre_delete_collection=True, # <--- MUY IMPORTANTE para prueba limpia
            create_extension=False
        )
        print("VectorStore PGVector principal listo.")
    except Exception as e_vs: print(f"ERROR CRÍTICO al init VectorStore: {e_vs}"); traceback.print_exc(); return

    async with AsyncSessionLocal_CRUD() as db_crud:
        print("Consultando ContextDefinitions activas...")
        stmt = (select(ContextDefinition).filter(ContextDefinition.is_active == True)
                .options(selectinload(ContextDefinition.document_sources),
                         selectinload(ContextDefinition.db_connections)))
        result = await db_crud.execute(stmt)
        active_contexts = result.scalars().unique().all()

        if not active_contexts: print("No hay ContextDefinitions activos."); return
        print(f"ContextDefinitions activos: {len(active_contexts)}")

        for ctx_def in active_contexts:
            print(f"\nProcesando Contexto: '{ctx_def.name}' (ID: {ctx_def.id}, Tipo: {ctx_def.main_type.value})")
            if main_vector_store is None: print("Error: main_vector_store no disponible."); continue

            if ctx_def.main_type == ContextMainType.DOCUMENTAL:
                if not ctx_def.document_sources: print(f"  Contexto '{ctx_def.name}' sin Orígenes de Documentos."); continue
                for doc_src_cfg in ctx_def.document_sources:
                    await process_document_source(doc_src_cfg, ctx_def, main_vector_store)
            elif ctx_def.main_type == ContextMainType.DATABASE_QUERY:
                await process_database_query_context(ctx_def, db_crud, main_vector_store)
            else:
                print(f"  Tipo de Contexto '{ctx_def.main_type.value}' no soportado para ingesta.")
        
        print("--- Pipeline de Ingesta Completado ---")

async def main():
    try:
        await run_ingestion_pipeline()
    finally:
        print("Cerrando motores de BD...")
        await async_engine_crud.dispose()
    print("Script de ingesta finalizado.")

if __name__ == "__main__":
    print("+++ Ejecutando script de INGESTA DE CONTEXTOS CONFIGURADOS +++")
    asyncio.run(main())