# mi_chatbot_ia/ingest_document.py
import asyncio
import os
import json
from typing import List, Dict, Any, Optional, Tuple
import traceback
import tempfile 
import shutil # Para borrar directorios recursivamente

# Langchain imports
from langchain_core.documents import Document as LangchainCoreDocument
from langchain_community.document_loaders import TextLoader
try: from langchain_community.document_loaders import PyPDFLoader
except ImportError: PyPDFLoader = None; print("INGEST_WARN: PyPDFLoader no disponible (pip install pypdf).")
try: from langchain_community.document_loaders import Docx2txtLoader
except ImportError: Docx2txtLoader = None; print("INGEST_WARN: Docx2txtLoader no disponible (pip install docx2txt).")
try: from langchain_community.document_loaders import UnstructuredExcelLoader
except ImportError: UnstructuredExcelLoader = None; print("INGEST_WARN: UnstructuredExcelLoader no disponible (pip install \"unstructured[xlsx]\" openpyxl).")

 
from custom_loaders import BatchedLineTextLoader  # <--- ASEGÚRATE DE QUE SE VEA ASÍ

# S3 imports
try:
    import boto3
    from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
except ImportError:
    boto3 = None # type: ignore
    NoCredentialsError = PartialCredentialsError = ClientError = Exception # Define placeholders
    print("INGEST_WARN: boto3 no disponible. Funcionalidad S3 no operativa (pip install boto3).")

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres.vectorstores import PGVector
from langchain_community.embeddings import SentenceTransformerEmbeddings

# SQLAlchemy y modelos
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import create_engine as sa_create_engine, text
from sqlalchemy.orm import sessionmaker as sa_sessionmaker
from sqlalchemy.sql import func

# Módulos de la aplicación
from app.db.session import AsyncSessionLocal_CRUD, async_engine_crud
from app.models.context_definition import ContextDefinition, ContextMainType
from app.models.document_source_config import DocumentSourceConfig, SupportedDocSourceType
from app.models.db_connection_config import DatabaseConnectionConfig, SupportedDBType
from app.utils.security_utils import decrypt_data
from app.config import settings
from app.tools.sql_tools2 import _get_sync_db_engine as get_external_sync_db_engine

# --- Configuración Global ---
MODEL_NAME_SBERT_FOR_EMBEDDING = settings.MODEL_NAME_SBERT_FOR_EMBEDDING
PGVECTOR_MAIN_COLLECTION_NAME = settings.PGVECTOR_CHAT_COLLECTION_NAME
DEFAULT_CHUNK_SIZE = 1000; DEFAULT_CHUNK_OVERLAP = 150
DEFAULT_DB_SCHEMA_CHUNK_SIZE = 2000; DEFAULT_DB_SCHEMA_CHUNK_OVERLAP = 200
S3_DOWNLOAD_BASE_TEMP_DIR = "C:/S3TempIngestCorrected" # <<--- ¡¡¡REVISA Y AJUSTA ESTA RUTA!!!

_sbert_embeddings_instance: Optional[SentenceTransformerEmbeddings] = None

def get_sbert_embeddings_instance() -> SentenceTransformerEmbeddings:
    global _sbert_embeddings_instance
    if _sbert_embeddings_instance is None: 
        _sbert_embeddings_instance = SentenceTransformerEmbeddings(model_name=MODEL_NAME_SBERT_FOR_EMBEDDING)
        print(f"INGEST_INFO: Instancia SBERT Embeddings '{MODEL_NAME_SBERT_FOR_EMBEDDING}' creada.")
    return _sbert_embeddings_instance

def fetch_data_from_db_for_ingest(db_conn_config: DatabaseConnectionConfig, query: str) -> List[Dict[str, Any]]:
    print(f"    DB_FETCH_INGEST: Conectando a '{db_conn_config.name}' (Tipo: {db_conn_config.db_type.value})")
    engine = None
    try:
        engine = get_external_sync_db_engine(db_conn_config, context_for_log="INGEST_FETCH_DATA_EXTERNAL")
        with engine.connect() as connection:
            result_proxy = connection.execute(text(query))
            results = [dict(row._mapping) for row in result_proxy.all()]
        print(f"    DB_FETCH_INGEST: Query OK, {len(results)} filas obtenidas.")
        return results
    except Exception as e_sa:
        print(f"    ERROR DB_FETCH_INGEST ('{db_conn_config.name}'): {type(e_sa).__name__} - {e_sa}")
        traceback.print_exc(limit=3)
        return []
    finally:
        if engine: engine.dispose()

# Definimos _process_single_file_from_path aquí arriba para que esté disponible
def _process_single_file_from_path(
    file_abs_path: str, 
    original_file_name_for_meta: str,
    s3_key_if_applicable: Optional[str],
    doc_source_model_obj: DocumentSourceConfig
) -> List[LangchainCoreDocument]:
    """Carga un archivo y devuelve documentos Langchain con metadatos enriquecidos."""
    loaded_file_docs: List[LangchainCoreDocument] = []
    loader_name_used: Optional[str] = None
    file_extension_lower = original_file_name_for_meta.lower().split('.')[-1] if '.' in original_file_name_for_meta else ''
    source_type_indicator = "(S3)" if s3_key_if_applicable else "(Local)"
    
    print(f"      _PROCESS_SINGLE_FILE: Procesando '{original_file_name_for_meta}' desde '{file_abs_path}'...")
    
    base_metadata_for_docs = {
        'source_filename': original_file_name_for_meta,
        'source_doc_source_id': doc_source_model_obj.id,
        'source_doc_source_name': doc_source_model_obj.name,
    }
    if s3_key_if_applicable:
        base_metadata_for_docs['source_s3_key'] = s3_key_if_applicable

    try:
        #
        # --- ### AQUÍ ESTÁ EL CAMBIO IMPORTANTE ### ---
        # Ahora usamos el loader que agrupa las líneas (BatchedLineTextLoader)
        #
        if original_file_name_for_meta.lower() in ['access.txt', 'error.txt']:
            print(f"        _PROCESS_SINGLE_FILE_INFO: Usando BatchedLineTextLoader para '{original_file_name_for_meta}' (agrupando de 10 en 10 líneas).")
            # Unimos 10 líneas por cada "documento". Esto reducirá 1.6M de items a 160k.
            loader = BatchedLineTextLoader(file_abs_path, batch_size=10, encoding='utf-8', metadata_template=base_metadata_for_docs)
            loaded_file_docs = list(loader.lazy_load()) 
            loader_name_used = f"BatchedLineText{source_type_indicator}"
        
        # El resto de la lógica para PDF, DOCX, etc., permanece igual.
        elif file_extension_lower in ['txt', 'md']: 
            loader = TextLoader(file_abs_path, encoding='utf-8'); loaded_file_docs = loader.load(); loader_name_used = "Text"
        elif file_extension_lower == 'pdf' and PyPDFLoader: 
            loader = PyPDFLoader(file_abs_path); loaded_file_docs = loader.load_and_split(); loader_name_used = "PDF"
        elif file_extension_lower == 'docx' and Docx2txtLoader: 
            loader = Docx2txtLoader(file_abs_path); loaded_file_docs = loader.load(); loader_name_used = "DOCX"
        elif file_extension_lower in ['xlsx', 'xls'] and UnstructuredExcelLoader: 
            loader = UnstructuredExcelLoader(file_abs_path, mode="elements"); loaded_file_docs = loader.load(); loader_name_used = "Excel"
        else:
            print(f"        _PROCESS_SINGLE_FILE_SKIP: Extensión '{file_extension_lower}' no soportada para '{original_file_name_for_meta}'.")
            return []

        if loader_name_used and loaded_file_docs:
            print(f"        _PROCESS_SINGLE_FILE_LOADED: '{original_file_name_for_meta}' ({loader_name_used}) -> {len(loaded_file_docs)} Langchain doc(s) generados.")
            
            # La lógica de metadatos no necesita el bucle 'for' para nuestro caso especial,
            # ya que el loader 'Batched' ya los asigna. Pero para los otros loaders sí es necesario.
            if 'BatchedLineText' not in loader_name_used:
                for i, doc_lc_item in enumerate(loaded_file_docs):
                    doc_lc_item.metadata = doc_lc_item.metadata or {}
                    combined_metadata = base_metadata_for_docs.copy()
                    combined_metadata.update(doc_lc_item.metadata) 
                    combined_metadata.update({
                        'loader_used': f"{loader_name_used}{source_type_indicator}",
                        'original_doc_index_in_file': i
                    })
                    if loader_name_used == "PDF" and 'page' in doc_lc_item.metadata: 
                        base_page_number = doc_lc_item.metadata.get('page') 
                        if isinstance(base_page_number, int) : combined_metadata['source_page_number'] = base_page_number + 1
                    
                    doc_lc_item.metadata = combined_metadata

        return loaded_file_docs
        
    except Exception as e_file_processing_error:
        print(f"      _PROCESS_SINGLE_FILE_ERROR: Procesando '{original_file_name_for_meta}' (path: {file_abs_path}): {type(e_file_processing_error).__name__} - {e_file_processing_error}")
        traceback.print_exc()
        return []

# Copia y pega esta función COMPLETA en tu archivo ingest_document3.py,
# reemplazando la versión anterior que tenías.

def process_document_source_content_sync( # Esta es la función síncrona principal para fuentes documentales
    doc_source: DocumentSourceConfig, 
    context_def: ContextDefinition,   
    vector_store: PGVector         
):
    print(f"  DOC_SRC_PROC: Origen '{doc_source.name}' (Tipo: {doc_source.source_type.value}) para Contexto '{context_def.name}'")
    all_loaded_lc_docs_for_this_source: List[LangchainCoreDocument] = [] 
    
    s3_source_specific_temp_dir: Optional[str] = None # Directorio temporal único para esta fuente S3

    try:
        #
        # --- NO HAY CAMBIOS EN ESTA PRIMERA PARTE (LÓGICA DE CARGA S3/LOCAL) ---
        #
        if doc_source.source_type == SupportedDocSourceType.LOCAL_FOLDER:
            cfg = doc_source.path_or_config
            if not (isinstance(cfg, dict) and "path" in cfg): print(f"    ERROR LOCAL_FOLDER: Falta 'path' en config para {doc_source.name}."); return
            folder_path = cfg["path"]
            if not os.path.isdir(folder_path): print(f"    ERROR LOCAL_FOLDER: Ruta '{folder_path}' no existe para {doc_source.name}."); return
            print(f"    LOCAL_FOLDER: Cargando de: {folder_path}")
            for item_filename in os.listdir(folder_path): # Renombrado a item_filename
                item_full_path = os.path.join(folder_path, item_filename)
                if os.path.isfile(item_full_path):
                    # Llamar al helper para procesar el archivo
                    all_loaded_lc_docs_for_this_source.extend(
                        _process_single_file_from_path(item_full_path, item_filename, None, doc_source)
                    )
        elif doc_source.source_type == SupportedDocSourceType.S3_BUCKET:
            if not boto3: print(f"    ERROR S3: Boto3 no instalado. Omitiendo fuente S3 '{doc_source.name}'."); return
            
            s3_path_or_config_dict = doc_source.path_or_config; s3_credentials_dict = {}
            s3_bucket_name_to_use = s3_path_or_config_dict.get("bucket") if isinstance(s3_path_or_config_dict, dict) else None
            if not s3_bucket_name_to_use and isinstance(s3_path_or_config_dict, dict):
                 s3_bucket_name_to_use = s3_path_or_config_dict.get("bucket_name")

            if not s3_bucket_name_to_use : print(f"   ERROR S3: Falta 'bucket' o 'bucket_name' en config para {doc_source.name}."); return
            s3_prefix_path_str = s3_path_or_config_dict.get("prefix", "").lstrip('/') if isinstance(s3_path_or_config_dict, dict) else ""
            
            if doc_source.credentials_info_encrypted: 
                decrypted_credentials_json_str = decrypt_data(doc_source.credentials_info_encrypted)
                if decrypted_credentials_json_str and decrypted_credentials_json_str != "[DATO ENCRIPTADO INVÁLIDO]": 
                    try: s3_credentials_dict = json.loads(decrypted_credentials_json_str)
                    except json.JSONDecodeError: print(f"      ERROR S3: JSON creds inválido para '{doc_source.name}'.")
                else: print(f"      ERROR S3: No se pudo desencriptar creds para '{doc_source.name}'.")
            
            s3_client_constructor_args = {k:v for k,v in s3_credentials_dict.items() if k in ["aws_access_key_id","aws_secret_access_key","region_name","aws_session_token"]}
            if not s3_client_constructor_args and not (os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")): 
                 print(f"    WARN S3: Sin creds para '{doc_source.name}'. Usando config de entorno/rol IAM si existe.")

            s3_source_specific_temp_dir = tempfile.mkdtemp(prefix=f"s3_ds_{doc_source.id}_", dir=S3_DOWNLOAD_BASE_TEMP_DIR)
            print(f"    S3_PROC: Bucket='{s3_bucket_name_to_use}', Prefijo='{s3_prefix_path_str}', Usando TempDirUnico: '{s3_source_specific_temp_dir}'")
            
            try:
                s3_boto_client = boto3.client('s3', **s3_client_constructor_args)
                s3_paginator = s3_boto_client.get_paginator('list_objects_v2'); s3_object_pages = s3_paginator.paginate(Bucket=s3_bucket_name_to_use, Prefix=s3_prefix_path_str)
                s3_files_processed_count = 0
                for s3_page in s3_object_pages:
                    for s3_object_item in s3_page.get("Contents", []):
                        s3_object_full_key_path = s3_object_item.get("Key")
                        
                        # Si no hay key o el objeto es una "carpeta" (termina en /), lo ignoramos.
                        if not s3_object_full_key_path or s3_object_full_key_path.endswith('/'):
                            continue 
                        
                        # [MEJORA] Creamos un nombre de archivo local único y seguro para evitar colisiones.
                        # Reemplazamos los separadores de ruta (/) por un carácter seguro (__)
                        # para aplanar la estructura de directorios en un solo directorio temporal.
                        # Ejemplo: 'BB/guia-estudiantes/manual.pdf' -> 'BB__guia-estudiantes__manual.pdf'
                        safe_local_filename = s3_object_full_key_path.replace('/', '__')
                        s3_local_temp_file_path = os.path.join(s3_source_specific_temp_dir, safe_local_filename)
                        
                        # [MEJORA] El nombre del archivo que guardaremos en los metadatos será la ruta completa de S3.
                        # Esto es mucho más informativo que solo el nombre base.
                        filename_for_metadata = s3_object_full_key_path
                        
                        try:
                            # Log actualizado para más claridad
                            print(f"      S3_DOWNLOAD: De '{s3_object_full_key_path}' -> A (temporal) '{s3_local_temp_file_path}'...")
                            
                            s3_boto_client.download_file(
                                s3_bucket_name_to_use, 
                                s3_object_full_key_path, 
                                s3_local_temp_file_path
                            )
                            
                            print(f"        S3_DOWNLOAD_OK: Archivo descargado.")
                            
                            # [MEJORA] Pasamos el nombre de archivo correcto para los metadatos.
                            all_loaded_lc_docs_for_this_source.extend(
                                _process_single_file_from_path(
                                    s3_local_temp_file_path,
                                    filename_for_metadata, # <- Ahora usamos la ruta completa.
                                    s3_object_full_key_path,
                                    doc_source
                                )
                            )
                            s3_files_processed_count += 1

                        except ClientError as e_s3_file_download_error:
                            print(f"        ERROR S3_DOWNLOAD para '{s3_object_full_key_path}': {e_s3_file_download_error}")
                        except Exception as e_s3_process_file_error:
                            # Log actualizado para más claridad
                            print(f"        ERROR Procesando archivo S3 '{filename_for_metadata}': {e_s3_process_file_error}")
                        finally:
                            # Limpieza del archivo temporal, crucial para no llenar el disco.
                            if os.path.exists(s3_local_temp_file_path):
                                try:
                                    os.remove(s3_local_temp_file_path)
                                except OSError as e:
                                    print(f"        WARN: No se pudo eliminar el archivo temporal '{s3_local_temp_file_path}': {e}")
                
                if s3_files_processed_count == 0: print(f"    S3_PROC: No se procesaron archivos desde S3 (Bucket: {s3_bucket_name_to_use}, Prefijo: {s3_prefix_path_str}). Verificar contenido o permisos S3.")
            except Exception as e_s3_listing_error:
                print(f"    ERROR S3 Principal (conexión/listado) para {doc_source.name}: {e_s3_listing_error}"); traceback.print_exc(limit=2)
    
    except Exception as e_outer_source_processing:
        print(f"  ERROR DOC_SRC_PROC: Excepción Mayor procesando fuente '{doc_source.name}': {e_outer_source_processing}")
        traceback.print_exc(limit=3)
    finally:
        if s3_source_specific_temp_dir and os.path.exists(s3_source_specific_temp_dir):
            try: shutil.rmtree(s3_source_specific_temp_dir); print(f"    S3_TEMP_CLEANUP: Directorio '{s3_source_specific_temp_dir}' eliminado.")
            except OSError as e_rmtree: print(f"    WARN S3_TEMP_CLEANUP: No se pudo eliminar dir temp '{s3_source_specific_temp_dir}': {e_rmtree}")

    #
    # --- ### OPTIMIZACIÓN ### INICIA LA SECCIÓN DE CÓDIGO MODIFICADO ---
    #

    if not all_loaded_lc_docs_for_this_source: 
        print(f"    DOC_SRC_PROC: No docs finales cargados de '{doc_source.name}' para chunkear."); return
    
    # Añadimos logs más claros para ver dónde estamos.
    print(f"    DOC_SRC_PROC: {len(all_loaded_lc_docs_for_this_source)} documentos cargados de los archivos fuente. Iniciando división (si es necesario)...")
    
    context_proc_cfg = context_def.processing_config or {}; 
    chunk_size = context_proc_cfg.get("chunk_size", DEFAULT_CHUNK_SIZE); chunk_overlap = context_proc_cfg.get("chunk_overlap", DEFAULT_CHUNK_OVERLAP)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    final_document_chunks = text_splitter.split_documents(all_loaded_lc_docs_for_this_source)
    
    if not final_document_chunks: 
        print(f"    DOC_SRC_PROC: No se generaron chunks finales de '{doc_source.name}'."); return

    print(f"    DOC_SRC_PROC: Se generaron {len(final_document_chunks)} chunks finales para '{doc_source.name}'. Añadiendo metadata...")
    
    # El bucle de metadatos no cambia.
    for chunk_instance in final_document_chunks: 
        chunk_instance.metadata = chunk_instance.metadata or {}
        chunk_instance.metadata.update({'context_id':context_def.id, 'context_name':str(context_def.name),'context_main_type':str(context_def.main_type.value)})
    
    try: 
        # Plan B: Ingesta manual por lotes para control y visibilidad
        total_chunks = len(final_document_chunks)
        manual_batch_size = 20000  # Haremos una transacción cada 20,000 chunks
        pgvector_batch_size = 1024 # El lote interno de PGVector

        print(f"    DOC_SRC_PROC: INICIANDO INGESTA MANUALMENTE DIVIDIDA. {total_chunks} chunks en transacciones de {manual_batch_size}.")

        for i in range(0, total_chunks, manual_batch_size):
            batch_to_ingest = final_document_chunks[i : i + manual_batch_size]
            print(f"      -> Procesando Lote de Transacción #{i//manual_batch_size + 1}: Chunks del {i} al {i+len(batch_to_ingest)-1}")
            
            # Cada llamada a add_documents es una transacción separada y más pequeña
            vector_store.add_documents(documents=batch_to_ingest, batch_size=pgvector_batch_size) 
            
            print(f"      -> Lote de Transacción #{i//manual_batch_size + 1} completado. Datos guardados en BD.")
            
        print(f"    DOC_SRC_PROC: INGESTA COMPLETADA. {total_chunks} chunks de '{doc_source.name}' (ctx: {context_def.name}) procesados.")
        
    except Exception as e_pg_add_final: 
        print(f"    ERROR DOC_SRC_PROC: Ingesta PGVector para '{doc_source.name}': {type(e_pg_add_final).__name__} - {e_pg_add_final}"); traceback.print_exc(limit=2)


async def process_database_query_context(context_def: ContextDefinition, vector_store: PGVector):
    print(f"  DB_SCHEMA_CTX_PROC: Contexto DATABASE_QUERY: '{context_def.name}' (ID: {context_def.id})")
    if not context_def.db_connection_config: print(f"    ERROR DB_SCHEMA: '{context_def.name}' no tiene db_connection_config."); return
    db_conn = context_def.db_connection_config; proc_cfg = context_def.processing_config  or {}
    dict_query = proc_cfg.get("dictionary_table_query")
    if not dict_query: print(f"    ERROR DB_SCHEMA: Falta 'dictionary_table_query' en '{context_def.name}'."); return
    print(f"    DB_SCHEMA_CTX_PROC: Usando Conexión '{db_conn.name}'. Query: {dict_query[:100]}...")
    schema_rows = await asyncio.to_thread(fetch_data_from_db_for_ingest, db_conn, dict_query)
    if not schema_rows: print(f"    ADVERTENCIA DB_SCHEMA: Query de diccionario sin datos para '{db_conn.name}'."); return
    print(f"    DB_SCHEMA_CTX_PROC: {len(schema_rows)} filas. Generando docs de esquema...")
    
    tables_info:Dict[Tuple[str,str],Dict[str,Any]]={};custom_table_descs=proc_cfg.get("custom_table_descriptions",{});def_desc=proc_cfg.get("table_description_template_default_desc","Tabla de datos del sistema.")
    col_tpl_str=proc_cfg.get("column_description_template","- Columna `{columna}` (Tipo: `{tipo}{longitud_str}` Nulos: `{permite_nulos_str}` Autonum: `{es_autonumerico_str}`): {col_descripcion_str}. {fk_info_str}")
    intro_tpl_str=proc_cfg.get("table_description_template_intro","Esquema para la tabla `{db_schema_name}`.`{db_table_name}`:\nDescripción: {table_custom_description_or_default}\nColumnas:")

    for r_data in schema_rows: # Renombrada para claridad
        schema_name_val=str(r_data.get("esquema","dbo")).strip(); table_name_val=str(r_data.get("tabla","")).strip(); col_name_val=str(r_data.get("columna","")).strip()
        if not table_name_val or not col_name_val: continue
        current_table_key=(schema_name_val,table_name_val)
        if current_table_key not in tables_info: tables_info[current_table_key]={"col_details_list": [], "db_schema_name": schema_name_val, "db_table_name": table_name_val, "eff_description": custom_table_descs.get(f"{schema_name_val}.{table_name_val}",def_desc)}
        
        col_type_str=str(r_data.get("tipo","N/A")).lower(); col_len_raw=r_data.get("longitud"); col_len_fmt_str = ""
        if col_len_raw is not None:
            try: 
                numeric_len = int(float(col_len_raw))
                if numeric_len == -1 or "max" in col_type_str: col_len_fmt_str = "(MAX)"
                elif numeric_len > 0: col_len_fmt_str = f"({numeric_len})"
            except (ValueError, TypeError): col_len_fmt_str = f"({str(col_len_raw).strip()})" if isinstance(col_len_raw, str) and str(col_len_raw).strip() else ""

        col_desc_val = str(r_data.get("descripcion","")).strip() or "Sin descripción específica."
        fk_target_table=str(r_data.get("ReferenceTableName","")).strip(); fk_target_col=str(r_data.get("ReferenceColumnName","")).strip()
        is_fk_indicator_val = r_data.get("ForeignKey"); is_fk_bool = bool(is_fk_indicator_val) or (isinstance(is_fk_indicator_val,str) and str(is_fk_indicator_val).strip().upper() in ["SI","S","Y","YES","TRUE","1"])
        fk_info_text_final = f"Es FK a `{fk_target_table}`.`{fk_target_col}`." if is_fk_bool and fk_target_table and fk_target_col else ""
        
        tables_info[current_table_key]["col_details_list"].append(col_tpl_str.format(
            columna=col_name_val, tipo=col_type_str, longitud_str=col_len_fmt_str, col_descripcion_str=col_desc_val, 
            fk_info_str=fk_info_text_final, permite_nulos_str=str(r_data.get("permite_nulos_vista","N/A")).upper(), 
            es_autonumerico_str=str(r_data.get("es_autonumerico_vista","N/A")).upper(),
            # Pasar todos los componentes al format por si el template los usa
            db_schema_name=schema_name_val, db_table_name=table_name_val, 
            fk_tabla_directo=fk_target_table, fk_col_directo=fk_target_col # Renombrados para evitar conflicto con los keys del format
        ))
    final_schema_langchain_docs:List[LangchainCoreDocument]=[];
    for(s_val,t_val), table_data_map in tables_info.items(): # Renombrados
        intro_text_formatted = intro_tpl_str.format(db_schema_name=s_val, db_table_name=t_val, table_custom_description_or_default=table_data_map["eff_description"])
        cols_text_formatted_block = "\n".join(table_data_map["col_details_list"])
        full_doc_content = f"{intro_text_formatted}\n{cols_text_formatted_block}"
        doc_metadata_map = {"source_type":"DATABASE_SCHEMA","db_connection_name":db_conn.name,"db_name_source":db_conn.database_name,"schema_name_source":s_val,"table_name_source":t_val}
        final_schema_langchain_docs.append(LangchainCoreDocument(page_content=full_doc_content,metadata=doc_metadata_map))
    
    if not final_schema_langchain_docs:print("    DB_SCHEMA_CTX_PROC: No docs de esquema generados.");return
    db_schema_cfg = proc_cfg # Alias
    db_schema_chunk_s = db_schema_cfg.get("db_schema_chunk_size",DEFAULT_DB_SCHEMA_CHUNK_SIZE); db_schema_chunk_o = db_schema_cfg.get("db_schema_chunk_overlap",DEFAULT_DB_SCHEMA_CHUNK_OVERLAP)
    schema_doc_splitter = RecursiveCharacterTextSplitter(chunk_size=db_schema_chunk_s,chunk_overlap=db_schema_chunk_o)
    final_schema_chunks_list = schema_doc_splitter.split_documents(final_schema_langchain_docs)
    if not final_schema_chunks_list:print("    DB_SCHEMA_CTX_PROC: No chunks de esquema.");return
    print(f"    DB_SCHEMA_CTX_PROC: Chunks de esquema: {len(final_schema_chunks_list)}. Añadiendo metadata...")
    for chunk_to_ingest in final_schema_chunks_list: chunk_to_ingest.metadata.update({'context_id':context_def.id,'context_name':str(context_def.name),'context_main_type':str(context_def.main_type.value)})
    try:vector_store.add_documents(documents=final_schema_chunks_list);print(f"    DB_SCHEMA_CTX_PROC: Chunks de '{context_def.name}' INGESTADOS.")
    except Exception as e_db_schema_ingest:print(f"    ERROR DB_SCHEMA_CTX_PROC: Ingesta: {e_db_schema_ingest}");traceback.print_exc(limit=2)


async def run_ingestion_pipeline():
    print(f"--- Iniciando Pipeline de Ingesta (Colección: {PGVECTOR_MAIN_COLLECTION_NAME}) ---")
    sbert_embeddings_instance = get_sbert_embeddings_instance()
    pgvector_sync_connection_string = settings.SYNC_DATABASE_VECTOR_URL 
    if not pgvector_sync_connection_string:
        print("ERROR CRÍTICO INGESTA: SYNC_DATABASE_VECTOR_URL no está configurada.")
        return
    
    main_vector_store_instance: Optional[PGVector] = None
    
    # --- INICIO DEL CÓDIGO CORREGIDO ---
    try:
        # Paso 1: Intentamos conectarnos a la colección como si ya existiera.
        # Es la forma más rápida si ya está creada.
        print(f"INGESTA: Intentando conectar a la colección existente '{PGVECTOR_MAIN_COLLECTION_NAME}'...")
        main_vector_store_instance = PGVector(
            connection=pgvector_sync_connection_string,
            embeddings=sbert_embeddings_instance,
            collection_name=PGVECTOR_MAIN_COLLECTION_NAME,
            use_jsonb=True,
            async_mode=False,
            create_extension=False,
        )
        print("INGESTA: Conexión a colección existente exitosa.")
        # La línea vector_store.get_collection() internamente verifica la existencia y falla si no está.
        # Para estar 100% seguros, podemos forzar una verificación, aunque el add_documents lo hará.
        # Por simplicidad, dejamos que falle en el `add_documents` y lo capture el except.

    except Exception as e:
        # Paso 2: Si el intento anterior falla (probablemente con "Collection not found"),
        # caemos aquí y la creamos explícitamente.
        print(f"INGESTA: La colección no existe o falló la conexión inicial ({e}). Procediendo a crearla...")
        try:
            # Esta es la forma explícita de añadir los primeros documentos,
            # lo que crea la colección si no existe.
            # Pasaremos una lista vacía de documentos; esto solo crea la colección sin añadir nada.
            main_vector_store_instance = PGVector.from_documents(
                documents=[], # Pasamos una lista vacía para solo crear la colección.
                embedding=sbert_embeddings_instance,
                collection_name=PGVECTOR_MAIN_COLLECTION_NAME,
                connection=pgvector_sync_connection_string,
                use_jsonb=True,
            )
            print("INGESTA: Nueva colección y VectorStore PGVector (SYNC) creados exitosamente.")
        except Exception as e_vs_init:
            print(f"ERROR CRÍTICO INGESTA: Fallo irrecuperable al inicializar VectorStore: {e_vs_init}")
            traceback.print_exc()
            return
            
    if main_vector_store_instance is None:
        print("ERROR CRÍTICO: No se pudo obtener una instancia del Vector Store después de todos los intentos.")
        return
    # --- FIN DEL CÓDIGO CORREGIDO ---

    # El resto de la función se mantiene exactamente igual.
    async with AsyncSessionLocal_CRUD() as async_db_crud_sess:
        print("INGESTA: Consultando ContextDefinitions activos...")
        query_stmt = (select(ContextDefinition).filter(ContextDefinition.is_active == True)
            .options(selectinload(ContextDefinition.document_sources), selectinload(ContextDefinition.db_connection_config),selectinload(ContextDefinition.default_llm_model_config),selectinload(ContextDefinition.virtual_agent_profile)))
        
        db_result = await async_db_crud_sess.execute(query_stmt)
        active_context_definitions = db_result.scalars().unique().all()

        if not active_context_definitions:
            print("INGESTA: No ContextDefinitions activos para procesar.")
            return
        print(f"INGESTA: {len(active_context_definitions)} ContextDefinitions activos encontrados.")

        for context_object in active_context_definitions:
            if main_vector_store_instance is None:
                print("ERROR: Vector Store no disponible.")
                break 
            
            print(f"\nINGESTA: Procesando Contexto: '{context_object.name}' (ID: {context_object.id}, Tipo: {context_object.main_type.value})")
            if context_object.main_type == ContextMainType.DOCUMENTAL:
                if not context_object.document_sources:
                    print(f"  INFO INGESTA: Contexto '{context_object.name}' (DOCUMENTAL) sin DocumentSources configurados.")
                    continue
                for doc_source_item in context_object.document_sources:
                    await asyncio.to_thread(process_document_source_content_sync, doc_source_item, context_object, main_vector_store_instance)
            elif context_object.main_type == ContextMainType.DATABASE_QUERY:
                await process_database_query_context(context_object, main_vector_store_instance) 
            else:
                print(f"  ADVERTENCIA INGESTA: Tipo de Contexto '{context_object.main_type.value}' no es soportado actualmente por este pipeline.")
        print("\n--- Pipeline de Ingesta Completado. ---")

async def main_ingest_script_entrypoint():
    # Crear S3_DOWNLOAD_BASE_TEMP_DIR al inicio si no existe Y si boto3 está disponible
    if boto3 and not os.path.exists(S3_DOWNLOAD_BASE_TEMP_DIR):
        try: os.makedirs(S3_DOWNLOAD_BASE_TEMP_DIR, exist_ok=True)
        except OSError as e_mkdir_main: print(f"ERROR_MAIN_INGEST: No se pudo crear directorio base para S3 temporal '{S3_DOWNLOAD_BASE_TEMP_DIR}': {e_mkdir_main}"); return
    
    try: await run_ingestion_pipeline()
    finally:
        print("INGESTA: Script de ingesta finalizado."); 
        if async_engine_crud: await async_engine_crud.dispose(); print("INGESTA: Engine de CRUD asíncrono (app) dispuesto.")
        # No hay _sync_crud_engine_for_ingest global, los engines síncronos se crean y disponen localmente.
            
if __name__ == "__main__":
    print("+++ Ejecutando SCRIPT DE INGESTA DE CONTEXTOS (Async Principal) +++")
    # Opcional: Configurar logging más detallado para debug
    # import logging
    # logging.basicConfig(level=logging.INFO)
    # logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO) # Para ver SQL de SQLAlchemy si se pone en INFO

    asyncio.run(main_ingest_script_entrypoint())