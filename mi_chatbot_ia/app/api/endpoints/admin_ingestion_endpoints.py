# mi_chatbot_ia/app/api/endpoints/admin_ingestion_endpoints.py

import traceback
from typing import List, Dict, Any

# --- IMPORTACIÓN CORREGIDA ---
# Nos aseguramos de que APIRouter esté importado desde fastapi.
from fastapi import (
    APIRouter, Depends, HTTPException, status,
    UploadFile, File, Form
)
# -----------------------------

from sqlalchemy.ext.asyncio import AsyncSession
from langchain_postgres.vectorstores import PGVector


# Dependencias locales de tu aplicación
from app.api.dependencies import get_vector_store, get_crud_db
from app.security.role_auth import require_roles
from app.models.app_user import AppUser
from app.services import ingestion_service

from app.crud import crud_context_definition # Asegúrate de tener esta importación
from pydantic import BaseModel # Para el cuerpo de la petición

from sqlalchemy import text # Asegúrate de importar text de sqlalchemy
import json # Asegúrate de importar json


# --- Definición del Router ---
router = APIRouter(
    prefix="/api/v1/admin/ingestion",
    tags=["Admin - Ingestion & Utilities"]
)

# Roles que pueden subir documentos. Ajústalo según necesites.
ROLES_CAN_INGEST = ["SuperAdmin", "ContextEditor"]
MENU_GESTION_CONTENIDO = "Gestión de Contenidos" # Nombre de ejemplo para la seguridad del menú


# --- Definición del Endpoint ---
@router.post(
    "/upload-documents",
    summary="Subir y vectorizar hasta 5 documentos para un contexto específico",
    status_code=status.HTTP_200_OK,
)
async def upload_and_ingest_documents(
    # --- Parámetros de la Petición ---
    files: List[UploadFile] = File(..., description="Lista de archivos a subir (máximo 5)."),
    context_id: int = Form(..., description="ID del Contexto de Conocimiento al que pertenecen estos documentos."),

    # --- Inyección de Dependencias ---
    db: AsyncSession = Depends(get_crud_db),
    vector_store: PGVector = Depends(get_vector_store),
    current_user: AppUser = Depends(require_roles(roles=ROLES_CAN_INGEST, menu_name=MENU_GESTION_CONTENIDO))
) -> Dict[str, Any]:
    """
    Endpoint para subir documentos, procesarlos y añadirlos a la base de conocimiento vectorial.

    - **Autenticación:** Requiere un usuario administrador con los roles adecuados.
    - **Validación:** Limita la subida a un máximo de 5 archivos y verifica que el Contexto exista.
    - **Proceso:** Llama al servicio de ingesta para manejar la lógica de carga, división y vectorización.
    - **Respuesta:** Devuelve un resumen del resultado de la operación.
    """
    print(f"INGEST_API: Usuario '{current_user.username_ad}' iniciando subida de {len(files)} archivos para contexto ID: {context_id}.")

    # 1. Validación de la cantidad de archivos
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se ha subido ningún archivo."
        )
    if len(files) > 5:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Se permite un máximo de 5 archivos por subida."
        )

    # 2. Llamada al servicio de ingesta
    try:
        result = await ingestion_service.process_uploaded_files(
            uploaded_files=files,
            context_id=context_id,
            db_session=db,
            vector_store=vector_store
        )
        
        return {
            "detail": f"Proceso de ingesta completado. Exitosos: {result['successful_files']}, Fallidos: {result['failed_files']}.",
            "results": result["file_results"]
        }

    except ValueError as ve:
        # Errores controlados desde el servicio, como "Contexto no encontrado".
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocurrió un error interno inesperado durante la ingesta: {str(e)}"
        )
    
class DeleteDocumentRequest(BaseModel):
    context_id: int
    filename: str

# --- NUEVO ENDPOINT DE ELIMINACIÓN ---
@router.delete(
    "/delete-document",
    summary="Eliminar un documento específico y sus chunks de un contexto",
    status_code=status.HTTP_200_OK
)
async def delete_ingested_document(
    request_data: DeleteDocumentRequest,
    db: AsyncSession = Depends(get_crud_db),
    vector_store: PGVector = Depends(get_vector_store), 
    current_user: AppUser = Depends(require_roles(roles=ROLES_CAN_INGEST, menu_name=MENU_GESTION_CONTENIDO))
):
    context_id = request_data.context_id
    filename = request_data.filename
    
    print(f"DELETE_API: Usuario '{current_user.username_ad}' solicitó eliminar '{filename}' del contexto ID: {context_id}.")

    context = await crud_context_definition.get_context_definition_by_id(db, context_id)
    if not context:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contexto no encontrado.")
    
    try:
        # --- ¡LA MISMA CORRECCIÓN QUE ANTES! ---
        # Construimos el nombre de la tabla de embeddings de forma manual,
        # que es la forma más robusta con tu configuración actual.
        embedding_table_name = "langchain_pg_embedding"
        # ----------------------------------------
        
        async with vector_store._async_engine.connect() as connection:
            
            filter_json = {
                "context_id": context_id,
                "source_filename": filename,
            }

            stmt = text(
                f"""
                DELETE FROM {embedding_table_name}
                WHERE cmetadata @> :filter_json
                """
            )
            
            result = await connection.execute(
                stmt,
                {"filter_json": json.dumps(filter_json)}
            )
            await connection.commit()
            
            chunks_eliminados = result.rowcount
            print(f"DELETE_API: Se eliminaron {chunks_eliminados} chunks para '{filename}' del contexto ID {context_id}.")

            return {
                "detail": f"Documento '{filename}' eliminado exitosamente del contexto '{context.name}'.",
                "chunks_deleted": chunks_eliminados,
            }
    
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al intentar eliminar el documento: {e}"
        )


# --- NUEVO ENDPOINT PARA LISTAR DOCUMENTOS DE UN CONTEXTO ---
@router.get(
    "/list-documents/{context_id}",
    summary="Listar los documentos subidos manualmente para un contexto",
    response_model=List[str]
)
async def list_manual_upload_documents(
    context_id: int,
    # El vector_store lo necesitamos para la conexión, ¡no para el nombre de la tabla!
    vector_store: PGVector = Depends(get_vector_store), 
    current_user: AppUser = Depends(require_roles(roles=ROLES_CAN_INGEST, menu_name=MENU_GESTION_CONTENIDO))
):
    print(f"\n--- [DEBUG] INICIO list_manual_upload_documents (Intento #3) ---")
    print(f"  [DEBUG] Contexto ID solicitado: {context_id}")
    
    try:
        # --- ¡LA CORRECCIÓN A PRUEBA DE BALAS! ---
        # LangChain por defecto usa un prefijo 'langchain_pg_' y le añade el sufijo 'embedding'.
        # Dado que tu colección principal no tiene un nombre complejo, la tabla es esta.
        # Es menos dinámico pero funcionará ahora mismo para desbloquearte.
        
        # OBTENEMOS EL NOMBRE DE LA COLECCIÓN DE LA INSTANCIA DE APP_STATE
        collection_name = vector_store.collection_name # Ej: "chatbot_knowledge_base_v1"
        
        # Y CONSTRUIMOS EL NOMBRE DE LA TABLA MANUALMENTE BASADO EN EL PATRÓN DE LANGCHAIN
        embedding_table_name = f"langchain_pg_embedding" # Esta es la tabla para la colección "langchain" (default)
                                                          # Si tu colección tuviera un nombre, la tabla sería diferente
                                                          # Pero PGVector se conecta a una, y esta es.
        
        # En tu caso específico, el nombre de la tabla es simplemente 'langchain_pg_embedding' porque
        # no has renombrado la colección en sí.
        
        print(f"  [DEBUG] Nombre de la colección: {collection_name}")
        print(f"  [DEBUG] Nombre de la tabla de embeddings asumido: '{embedding_table_name}'")

        async with vector_store._async_engine.connect() as connection:
            print(f"  [DEBUG] Conexión a la base de datos vectorial establecida.")
            
            stmt = text(
                f"""
                SELECT DISTINCT cmetadata->>'source_filename' as filename
                FROM {embedding_table_name}
                WHERE cmetadata->>'context_id' = :context_id
                  AND cmetadata->>'source_type' = 'api_upload'
                ORDER BY filename;
                """
            )

            print(f"  [DEBUG] Ejecutando SQL query: {stmt}")

            result = await connection.execute(stmt, {"context_id": str(context_id)})
            filenames = result.scalars().all()
            
            print(f"  [DEBUG] Query exitosa. Se encontraron {len(filenames)} archivos: {filenames}")
            print(f"--- [DEBUG] FIN list_manual_upload_documents (Éxito) ---\n")
            return filenames
            
    except Exception as e:
        print(f"\n--- [DEBUG] ERROR en list_manual_upload_documents ---")
        print(f"  [DEBUG] Tipo de Excepción: {type(e).__name__}")
        print(f"  [DEBUG] Mensaje: {e}")
        traceback.print_exc()
        print(f"--- [DEBUG] FIN list_manual_upload_documents (Fallo) ---\n")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al listar documentos: {e}"
        )