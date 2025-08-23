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

# --- FUNCIONES INTERNAS DEL SERVICIO ---

def _get_loader_and_load_docs(file_path: str, original_filename: str) -> List[LangchainCoreDocument]:
    """
    Selecciona el loader apropiado de LangChain. Modifica el entorno de ejecución
    SOLO si detecta que está corriendo en Windows para asegurar la compatibilidad.
    """
    
    # --- BLOQUE DE COMPATIBILIDAD PARA WINDOWS ---
    # Este 'if' es la clave: solo se ejecuta si el S.O. es Windows ('nt' de new technology).
    if os.name == 'nt':
        print("INGEST_SERVICE_DEBUG: Entorno Windows detectado. Estableciendo rutas para OCR...")
        
        # Rutas locales para tu máquina Windows
        poppler_bin_path = r'C:\poppler\bin'  # Asegúrate de que esta sea la ruta correcta a la carpeta 'bin' de Poppler
        tesseract_dir_path = r'C:\OCR' # La nueva ruta SIN espacios que instalaste

        original_path = os.environ.get('PATH', '')
        tessdata_dir = os.path.join(tesseract_dir_path, 'tessdata')
        
        # Establecemos las variables de entorno que necesita Tesseract en Windows
        os.environ['TESSDATA_PREFIX'] = tessdata_dir
        os.environ['PATH'] = f"{poppler_bin_path};{tesseract_dir_path};{original_path}"
        
        print(f"INGEST_SERVICE_DEBUG: TESSDATA_PREFIX fijado a '{tessdata_dir}'")
        print(f"INGEST_SERVICE_DEBUG: PATH temporalmente modificado.")
    # En Linux, este bloque de código simplemente NO se ejecuta.
    # -----------------------------------------------

    if not UnstructuredFileLoader or not UnstructuredExcelLoader:
        raise ImportError("Las librerías 'unstructured' son necesarias.")

    file_extension = original_filename.lower().split('.')[-1]
    loader = None
    
    if file_extension in ['pdf', 'docx', 'doc', 'txt', 'md', 'jpg', 'jpeg', 'png', 'webp']:
        loader = UnstructuredFileLoader(
            file_path,
            mode="elements",
            strategy="hi_res",
            languages=["spa"]
        )
    elif file_extension in ['xlsx', 'xls']:
        loader = UnstructuredExcelLoader(file_path, mode="elements")
    
    if not loader:
        raise ValueError(f"Tipo de archivo no soportado: '{file_extension}'")

    print(f"INGEST_SERVICE_INFO: Cargando contenido de '{original_filename}'. Puede tardar...")
    docs = loader.load()
    print(f"INGEST_SERVICE_INFO: '{original_filename}' cargado, se extrajeron {len(docs)} elementos.")

    # Restaurar el PATH es una buena práctica después de haber terminado con el loader
    if os.name == 'nt' and 'original_path' in locals():
        os.environ['PATH'] = original_path
        if 'TESSDATA_PREFIX' in os.environ:
            del os.environ['TESSDATA_PREFIX']

    return docs

# --- FUNCIÓN PRINCIPAL DEL SERVICIO (no cambia, pero se incluye para que el archivo esté completo) ---

async def process_uploaded_files(
    uploaded_files: List[UploadFile],
    context_id: int,
    db_session: AsyncSession,
    vector_store: PGVector
) -> Dict[str, Any]:
    context_def = await crud_context_definition.get_context_definition_by_id(db_session, context_id)
    if not context_def:
        raise ValueError(f"El ContextDefinition con ID {context_id} no fue encontrado.")
    
    print(f"INGEST_SERVICE: Iniciando ingesta para contexto: '{context_def.name}' (ID: {context_id})")
    
    results_summary = {
        "successful_files": 0, "failed_files": 0, "total_chunks_ingested": 0,
        "file_results": []
    }
    all_docs_from_all_files: List[LangchainCoreDocument] = []
    
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
                        'context_name': context_def.name,
                        'context_id': context_def.id,
                        'context_main_type': context_def.main_type.value,
                        'source_filename': uploaded_file.filename,
                        'source_type': 'api_upload'
                    })
                    if 'page_number' in doc.metadata:
                        doc.metadata['source_page_number'] = doc.metadata.get('page_number')

                all_docs_from_all_files.extend(loaded_docs)
                file_result["status"] = "success"
                results_summary["successful_files"] += 1

            except Exception as e:
                error_message = f"{type(e).__name__}: {e}"
                print(f"ERROR_INGEST_SERVICE: Fallo procesando archivo '{uploaded_file.filename}'. Error: {error_message}")
                traceback.print_exc(limit=2)
                file_result["error"] = error_message
                results_summary["failed_files"] += 1
            
            finally:
                uploaded_file.file.close()
                results_summary["file_results"].append(file_result)
        
        if not all_docs_from_all_files:
            return results_summary
            
        print(f"INGEST_SERVICE: {len(all_docs_from_all_files)} elementos cargados. Dividiendo en chunks...")

        context_proc_cfg = context_def.processing_config or {}
        chunk_size = context_proc_cfg.get("chunk_size", DEFAULT_CHUNK_SIZE)
        chunk_overlap = context_proc_cfg.get("chunk_overlap", DEFAULT_CHUNK_OVERLAP)
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        final_chunks = text_splitter.split_documents(all_docs_from_all_files)
        
        if not final_chunks: return results_summary
        
        print(f"INGEST_SERVICE: {len(final_chunks)} chunks generados. Vectorizando y guardando...")

        try:
            await vector_store.aadd_documents(documents=final_chunks, ids=None)
            results_summary["total_chunks_ingested"] = len(final_chunks)
            print("INGEST_SERVICE: ¡Ingesta en PGVector completada!")
        except Exception as e:
            print("ERROR_INGEST_SERVICE: Fallo crítico al guardar chunks en la base de datos vectorial.")
            traceback.print_exc()
            raise RuntimeError(f"Fallo al guardar en PGVector: {e}")

    return results_summary