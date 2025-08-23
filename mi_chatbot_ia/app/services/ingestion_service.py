# mi_chatbot_ia/app/services/ingestion_service.py
import os
import shutil
import tempfile
import traceback
from typing import List, Dict, Any

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.documents import Document as LangchainCoreDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres.vectorstores import PGVector

# Imports para Carga Avanzada y OCR
try:
    from langchain_community.document_loaders import UnstructuredFileLoader, UnstructuredExcelLoader
except ImportError:
    UnstructuredFileLoader, UnstructuredExcelLoader = None, None
    print("INGEST_SERVICE_WARN: unstructured loaders no disponibles.")

# CRUD y Configuración
from app.crud import crud_context_definition

# --- CONSTANTES ---
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150

# --- CONFIGURACIÓN DE ENTORNO PARA WINDOWS ---
# Se ejecuta una sola vez al importar el módulo.
# No afecta a entornos Linux como Render.
if os.name == 'nt':
    print("INGEST_SERVICE_SETUP: Entorno Windows detectado. Configurando rutas para OCR.")
    poppler_bin_path = r'C:\poppler\bin'
    tesseract_dir_path = r'C:\OCR' # O la ruta donde lo instalaste

    if not os.path.isdir(poppler_bin_path):
        print(f"ADVERTENCIA DE INGESTA: No se encontró el directorio de Poppler en '{poppler_bin_path}'")
    if not os.path.isdir(tesseract_dir_path):
        print(f"ADVERTENCIA DE INGESTA: No se encontró el directorio de Tesseract en '{tesseract_dir_path}'")

    original_path = os.environ.get('PATH', '')
    tessdata_dir = os.path.join(tesseract_dir_path, 'tessdata')
    
    os.environ['TESSDATA_PREFIX'] = tessdata_dir
    os.environ['PATH'] = f"{poppler_bin_path};{tesseract_dir_path};{original_path}"
    print("INGEST_SERVICE_SETUP: Rutas de OCR añadidas al entorno de ejecución para este proceso.")

# --- Función Interna de Carga de Documentos ---
def _get_loader_and_load_docs(file_path: str, original_filename: str) -> List[LangchainCoreDocument]:
    if not UnstructuredFileLoader:
        raise ImportError("La librería 'unstructured' es necesaria para esta funcionalidad.")

    file_extension = original_filename.lower().split('.')[-1]
    loader = None
    
    # Parámetros para Unstructured
    unstructured_kwargs = {
        "mode": "elements",
        "strategy": "auto",  # Estrategia automática que decide si usar OCR
        "languages": ["spa"]
    }

    # Asignación de loader según el tipo de archivo
    if file_extension in ['pdf', 'docx', 'doc', 'txt', 'md', 'jpg', 'jpeg', 'png', 'webp']:
        loader = UnstructuredFileLoader(file_path, **unstructured_kwargs)
    elif file_extension in ['xlsx', 'xls'] and UnstructuredExcelLoader:
        loader = UnstructuredExcelLoader(file_path, mode="elements")
    else:
        raise ValueError(f"Tipo de archivo no soportado: '{file_extension}'")

    print(f"INGEST_SERVICE_INFO: Cargando '{original_filename}' con la estrategia '{loader.strategy if hasattr(loader, 'strategy') else 'default'}'.")
    docs = loader.load()
    print(f"INGEST_SERVICE_INFO: '{original_filename}' cargado, se extrajeron {len(docs)} elementos.")
    return docs

# --- Función Principal del Servicio ---
async def process_uploaded_files(
    uploaded_files: List[UploadFile],
    context_id: int,
    db_session: AsyncSession,
    vector_store: PGVector
) -> Dict[str, Any]:
    """
    Servicio principal que procesa, limpia y vectoriza archivos, optimizado para memoria
    y robusto contra caracteres NUL.
    """
    context_def = await crud_context_definition.get_context_definition_by_id(db_session, context_id)
    if not context_def:
        raise ValueError(f"ContextDefinition con ID {context_id} no fue encontrado.")
    
    print(f"INGEST_SERVICE: Iniciando ingesta secuencial para contexto: '{context_def.name}'")
    
    results_summary = {"successful_files": 0, "failed_files": 0, "total_chunks_ingested": 0, "file_results": []}
    
    context_proc_cfg = context_def.processing_config or {}
    chunk_size = context_proc_cfg.get("chunk_size", DEFAULT_CHUNK_SIZE)
    chunk_overlap = context_proc_cfg.get("chunk_overlap", DEFAULT_CHUNK_OVERLAP)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    with tempfile.TemporaryDirectory(prefix="ingest_upload_") as temp_dir:
        for uploaded_file in uploaded_files:
            file_path = os.path.join(temp_dir, uploaded_file.filename)
            file_result = {"filename": uploaded_file.filename, "status": "failed", "error": ""}
            
            try:
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(uploaded_file.file, buffer)
                
                loaded_docs = _get_loader_and_load_docs(file_path, uploaded_file.filename)
                
                for doc in loaded_docs:
                    doc.metadata = doc.metadata or {}
                    doc.metadata.update({
                        'context_name': context_def.name, 'context_id': context_def.id,
                        'source_filename': uploaded_file.filename, 'source_type': 'api_upload',
                    })
                
                chunks_for_this_file = text_splitter.split_documents(loaded_docs)

                if chunks_for_this_file:
                    # --- CORRECCIÓN DE LA LIMPIEZA (FORMA LEGIBLE Y SEGURA) ---
                    chunks_limpios = []
                    for chunk in chunks_for_this_file:
                        # Reemplaza el carácter NUL ('\x00') que PostgreSQL no acepta
                        chunk.page_content = chunk.page_content.replace('\x00', '')
                        chunks_limpios.append(chunk)
                    # -----------------------------------------------------------
                    
                    if chunks_limpios:
                        print(f"INGEST_SERVICE: Ingestando {len(chunks_limpios)} chunks limpios de '{uploaded_file.filename}'...")
                        await vector_store.aadd_documents(documents=chunks_limpios, ids=None)
                        results_summary["total_chunks_ingested"] += len(chunks_limpios)

                file_result["status"] = "success"
                results_summary["successful_files"] += 1
            except Exception as e:
                error_message = f"{type(e).__name__}: {e}"
                file_result["error"] = error_message
                results_summary["failed_files"] += 1
                traceback.print_exc()
            finally:
                uploaded_file.file.close()
                results_summary["file_results"].append(file_result)

    print(f"INGEST_SERVICE: Proceso de ingesta finalizado.")
    return results_summary