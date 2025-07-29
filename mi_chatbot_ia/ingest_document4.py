# mi_chatbot_ia/ingest_document.py
import asyncio
import os
import json
import traceback
import tempfile
import shutil

# [REFACTOR-OCR] Imports para OCR
import PIL.Image
try:
    import pytesseract
    # [IMPORTANTE] Descomenta y ajusta la siguiente línea si Tesseract no está en tu PATH
    # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except ImportError:
    pytesseract = None
    print("INGEST_WARN: pytesseract no disponible. Funcionalidad OCR no operativa (pip install pytesseract).")

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
    print("INGEST_WARN: PyMuPDF (fitz) no disponible. Funcionalidad PDF avanzada/OCR no operativa (pip install PyMuPDF).")


# Langchain imports (el resto se mantiene igual)
# ... (tus imports de LangChain)
from langchain_core.documents import Document as LangchainCoreDocument


# ... (resto de tus imports de SQLAlchemy, modelos, etc. sin cambios)
from app.models.document_source_config import DocumentSourceConfig


# --- Configuración y Funciones Auxiliares (sin cambios en la mayoría) ---
# ... (get_sbert_embeddings_instance, fetch_data_from_db_for_ingest) ...


# ==========================================================
# ======>      LÓGICA DE CARGA DE ARCHIVOS REFACTORIZADA (OCR+MT)      <======
# ==========================================================
def _process_pdf_with_ocr_sync(
    file_path: str,
    metadata_base: Dict[str, Any]
) -> List[LangchainCoreDocument]:
    """Carga un PDF, intentando OCR en páginas basadas en imágenes."""
    if not fitz:
        print("      _PROCESS_PDF_ERROR: PyMuPDF (fitz) no está instalado. No se puede procesar el PDF.")
        return []

    docs = []
    print(f"      _PROCESS_PDF: Abriendo (PyMuPDF) '{metadata_base.get('source_filename', 'N/A')}'")
    pdf_document = fitz.open(file_path)
    
    for page_num, page in enumerate(pdf_document):
        # 1. Intentar extraer texto directamente
        text = page.get_text()
        
        # 2. Si no hay mucho texto, podría ser una imagen. Intentar OCR.
        if len(text.strip()) < 100: # Umbral configurable, si hay poco texto, asumimos imagen.
            if pytesseract:
                print(f"        -> Página {page_num + 1} tiene poco texto. Intentando OCR...")
                try:
                    # Renderizar página a imagen de alta resolución para mejor OCR
                    pix = page.get_pixmap(dpi=300)
                    img = PIL.Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    ocr_text = pytesseract.image_to_string(img, lang='spa+eng') # Asume español e inglés
                    
                    if ocr_text.strip():
                        print(f"        -> OCR exitoso en página {page_num + 1}.")
                        text = ocr_text # Reemplazamos el texto vacío con el texto de OCR
                    else:
                        print(f"        -> OCR en página {page_num + 1} no extrajo texto.")
                except Exception as e_ocr:
                    print(f"        -> ERROR de OCR en página {page_num + 1}: {e_ocr}")
            else:
                 print(f"        -> Página {page_num + 1} parece imagen, pero pytesseract no está disponible.")

        if text.strip():
            page_metadata = metadata_base.copy()
            page_metadata['source_page_number'] = page_num + 1
            docs.append(LangchainCoreDocument(page_content=text, metadata=page_metadata))
            
    pdf_document.close()
    return docs

def _process_single_file_from_path(
    file_abs_path: str, 
    original_file_name_for_meta: str,
    # [REFACTOR-MT] Parámetro añadido
    base_metadata_for_docs: Dict[str, Any]
) -> List[LangchainCoreDocument]:
    """Carga un archivo y devuelve documentos Langchain con metadatos enriquecidos."""
    # (El resto de la lógica de carga para otros tipos de archivo (TXT, DOCX, etc.) va aquí,
    # similar a como lo tenías, pero usando `base_metadata_for_docs` en lugar de crearlo adentro.)
    
    # ... Tu lógica para TextLoader, Docx2txtLoader, etc ...
    # Aquí un ejemplo para PDF usando la nueva función OCR
    
    file_extension_lower = original_file_name_for_meta.lower().split('.')[-1]
    
    if file_extension_lower == 'pdf':
        return _process_pdf_with_ocr_sync(file_abs_path, base_metadata_for_docs)
    
    # Aquí pondrías el resto de tus `elif` para otros tipos de archivo,
    # asegurándote de que todos usen y extiendan el `base_metadata_for_docs`.
    # elif file_extension_lower == 'docx':
    #     ...
    
    return []

# =========================================================================
# ======>   PIPELINE DE INGESTA REFACTORIZADO PARA MULTI-TENANCY    <======
# =========================================================================
# He unificado `process_document_source_content_sync` y `process_database_query_context` dentro
# de una nueva función orquestadora.

async def ingest_source_for_client(
    source_config_id: int, 
    api_client_id: int, 
    db_session: AsyncSession,
    vector_store: PGVector
):
    """
    Ingesta una fuente de datos específica para un cliente específico.
    Esta función es el núcleo de la sincronización a demanda.
    """
    print(f"\n--- INGESTA A DEMANDA: Fuente ID={source_config_id} para Cliente ID={api_client_id} ---")
    
    # 1. Obtener la fuente y el contexto al que pertenece para este cliente
    source_query = select(DocumentSourceConfig).filter(DocumentSourceConfig.id == source_config_id)
    source_result = await db_session.execute(source_query)
    source_obj = source_result.scalars().first()
    
    if not source_obj:
        print(f"  ERROR: No se encontró la fuente de datos con ID {source_config_id}.")
        return

    # Encuentra a qué contexto está asociada esta fuente
    # Esta es una consulta simplificada; en un sistema complejo, necesitarías JOINs.
    context_query = select(ContextDefinition).filter(ContextDefinition.document_sources.any(id=source_config_id))
    context_result = await db_session.execute(context_query)
    context_obj = context_result.scalars().first()

    if not context_obj:
        print(f"  ERROR: No se encontró un contexto asociado a la fuente ID {source_config_id}.")
        return

    # 2. Borrar datos antiguos para esta fuente y este cliente
    # Esto asegura que la sincronización siempre tenga los datos más frescos.
    print(f"  BORRANDO DATOS ANTIGUOS: Limpiando chunks de fuente ID {source_config_id} para cliente ID {api_client_id}...")
    await asyncio.to_thread(
        vector_store.delete, 
        filter={
            "source_doc_source_id": {"$eq": source_config_id},
            "api_client_id": {"$eq": api_client_id}
        }
    )
    print("  BORRADO COMPLETADO.")

    # 3. Preparar metadatos base con el ID del cliente
    base_metadata = {
        "context_id": context_obj.id,
        "context_name": str(context_obj.name),
        "api_client_id": api_client_id, # <-- LA ETIQUETA DE MULTI-TENANCY
        "source_doc_source_id": source_obj.id,
        "source_doc_source_name": source_obj.name,
    }
    
    all_loaded_lc_docs: List[LangchainCoreDocument] = []
    
    # 4. Lógica de carga (S3/Local), similar a la tuya pero simplificada y usando `base_metadata`
    if source_obj.source_type == SupportedDocSourceType.LOCAL_FOLDER:
        # Tu lógica para recorrer archivos en una carpeta local
        folder_path = source_obj.path_or_config.get("path")
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                # Añadimos el nombre del archivo a los metadatos antes de procesar
                file_specific_metadata = base_metadata.copy()
                file_specific_metadata["source_filename"] = filename
                all_loaded_lc_docs.extend(
                    _process_single_file_from_path(file_path, filename, file_specific_metadata)
                )

    # 5. Dividir en chunks
    context_proc_cfg = context_obj.processing_config or {}
    chunk_size = context_proc_cfg.get("chunk_size", DEFAULT_CHUNK_SIZE)
    chunk_overlap = context_proc_cfg.get("chunk_overlap", DEFAULT_CHUNK_OVERLAP)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    final_document_chunks = text_splitter.split_documents(all_loaded_lc_docs)
    
    # 6. Añadir metadatos finales (redundante pero seguro) y guardar
    if final_document_chunks:
        for chunk in final_document_chunks:
            # Sobreescribimos/aseguramos que los metadatos correctos están presentes
            chunk.metadata.update(base_metadata)
            
        print(f"  INGESTANDO: {len(final_document_chunks)} chunks para fuente '{source_obj.name}'...")
        await asyncio.to_thread(vector_store.add_documents, documents=final_document_chunks)
        print("  INGESTA COMPLETADA con éxito.")

# ================================================================
# ======>   Punto de Entrada Principal (para ingesta masiva)    <======
# ================================================================

async def run_full_ingestion_pipeline(specific_api_client_id: Optional[int] = None):
    """
    Orquesta la ingesta de TODAS las fuentes para TODOS los clientes,
    o para un cliente específico si se proporciona un ID.
    """
    # ... (Inicialización de sbert_embeddings y vector_store como lo tenías) ...
    vector_store = ...

    async with AsyncSessionLocal_CRUD() as db_session:
        # 1. Determinar para qué clientes vamos a ingestar
        api_clients_to_process = []
        if specific_api_client_id:
            # Lógica para obtener un solo cliente
            pass
        else:
            # Lógica para obtener TODOS los clientes activos
            print("INGESTA MASIVA: Obteniendo todos los clientes activos...")
            client_query = select(ApiClient) # Simplificado, necesitas el modelo ApiClient
            # ...
        
        # 2. Iterar sobre cada cliente
        for client in api_clients_to_process:
            print(f"\n===== PROCESANDO CLIENTE: {client.name} (ID: {client.id}) =====")
            # 3. Obtener todas las fuentes de documentos a las que este cliente tiene acceso
            #    (a través de sus contextos permitidos)
            document_sources_for_client = ... # Esta consulta es compleja (JOINs)
            
            for source in document_sources_for_client:
                # 4. Llamar a la función de ingesta granular
                await ingest_source_for_client(
                    source_config_id=source.id,
                    api_client_id=client.id,
                    db_session=db_session,
                    vector_store=vector_store
                )
    print("\n--- Pipeline de Ingesta Masiva Completado ---")

async def main():
    # El punto de entrada ahora puede decidir si hacer una ingesta total
    # o una específica, por ejemplo, leyendo argumentos de línea de comando.
    await run_full_ingestion_pipeline()


if __name__ == "__main__":
    asyncio.run(main())