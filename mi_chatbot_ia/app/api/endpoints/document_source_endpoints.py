# app/api/document_source_endpoints.py
from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession # type: ignore
from typing import List

from app.db.session import get_crud_db_session
from app.schemas.schemas import (
    DocumentSourceCreate,
    DocumentSourceUpdate,
    DocumentSourceResponse
)
from app.crud import crud_document_source
# Asegúrate de que app.crud.crud_document_source contenga get_document_source_by_name
from app.models.app_user import AppUser 
from app.security.role_auth import require_roles

# Ejemplo para context_definition_endpoints.py
menu_name=MENU_DOC_SOURCES = ["SuperAdmin", "DocumentEditor"] # Quizás ContextEditor también puede gestionar contextos
ROLES_VIEW_CONTEXTS = ["SuperAdmin", "ContextEditor", "LogViewer"] 

MENU_DOC_SOURCES = "Fuentes de Documentos"

router = APIRouter(
    prefix="/api/v1/admin/doc_sources", # Prefijo para estos endpoints de admin
    tags=["Admin - Document Sources"]    # Etiqueta para Swagger UI
)

@router.post("/", response_model=DocumentSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_new_document_source(
    source_in: DocumentSourceCreate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_DOC_SOURCES)) # O SUPERADMIN_ONLY
):
    # Tu lógica actual, pero ahora con current_user disponible y permisos verificados
    print(f"CONTEXT_DEF_API: Admin '{current_user.username_ad}' creando Documents.")
    """
    Crea una nueva configuración de origen de documentos.
    Las credenciales (si se proveen) se encriptarán.
    """
    existing_source = await crud_document_source.get_document_source_by_name(db, name=source_in.name)
    if existing_source:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un origen de documentos con el nombre '{source_in.name}'."
        )
    
    new_source = await crud_document_source.create_document_source(db=db, source_in=source_in)
    return new_source


@router.get("/", response_model=List[DocumentSourceResponse])
async def read_all_document_sources(
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_DOC_SOURCES)) # O SUPERADMIN_ONLY
):
    # Tu lógica actual, pero ahora con current_user disponible y permisos verificados
    print(f"CONTEXT_DEF_API: Admin '{current_user.username_ad}' creando Documents.")
    """
    Obtiene una lista de todas las configuraciones de orígenes de documentos.
    (No se devuelven credenciales).
    """
    sources = await crud_document_source.get_document_sources(db=db, skip=skip, limit=limit)
    return sources


@router.get("/{source_id}", response_model=DocumentSourceResponse)
async def read_document_source_by_id(
    source_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_DOC_SOURCES)) # O SUPERADMIN_ONLY
):
    # Tu lógica actual, pero ahora con current_user disponible y permisos verificados
    print(f"CONTEXT_DEF_API: Admin '{current_user.username_ad}' Obteniendo Documents.""/{source_id}")
    """
    Obtiene una configuración de origen de documentos por su ID.
    (No se devuelven credenciales).
    """
    db_source = await crud_document_source.get_document_source_by_id(db=db, source_id=source_id)
    if db_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Origen de documentos no encontrado.")
    return db_source


@router.put("/{source_id}", response_model=DocumentSourceResponse)
async def update_existing_document_source(
    source_id: int,
    source_update: DocumentSourceUpdate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_DOC_SOURCES)) # O SUPERADMIN_ONLY
):
    # Tu lógica actual, pero ahora con current_user disponible y permisos verificados
    print(f"CONTEXT_DEF_API: Admin '{current_user.username_ad}' Actualizando Documents.""/{source_id}")
    """
    Actualiza una configuración de origen de documentos existente.
    Si se proveen nuevas credenciales, se encriptarán y reemplazarán las anteriores.
    """
    db_source = await crud_document_source.get_document_source_by_id(db=db, source_id=source_id)
    if db_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Origen de documentos no encontrado.")
    
    if source_update.name and source_update.name != db_source.name:
        existing_name_source = await crud_document_source.get_document_source_by_name(db, name=source_update.name)
        if existing_name_source and existing_name_source.id != source_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe otro origen de documentos con el nombre '{source_update.name}'."
            )

    updated_source = await crud_document_source.update_document_source(db=db, db_source_obj=db_source, source_in=source_update)
    return updated_source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_source_entry(
    source_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(menu_name=MENU_DOC_SOURCES)) # O SUPERADMIN_ONLY
):
    # Tu lógica actual, pero ahora con current_user disponible y permisos verificados
    print(f"CONTEXT_DEF_API: Admin '{current_user.username_ad}' Eliminando Documents.""/{source_id}")
    """
    Elimina una configuración de origen de documentos.
    """
    deleted_source = await crud_document_source.delete_document_source(db=db, source_id=source_id)
    if deleted_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Origen de documentos no encontrado.")
    return None