# app/api/endpoints/context_definition_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import json

# --- Importaciones clave para la depuración ---
from pydantic import ValidationError

from app.db.session import get_crud_db_session
from app.schemas.schemas import (
    ContextDefinitionCreate,
    ContextDefinitionUpdate,
    ContextDefinitionResponse,
    ContextMainType
)
from app.crud import crud_context_definition
from app.models.app_user import AppUser 
from app.security.role_auth import require_roles

ROLES_MANAGE_CONTEXTS = ["SuperAdmin", "ContextEditor"]
# Asumiendo que esta variable MENU_CONTEXTS es usada por tu decorador de roles
# y los roles que pueden ver son estos. Si no, ajústalo.
ROLES_CAN_VIEW = ["SuperAdmin", "ContextEditor", "ApiClientManager", "LogViewer"]
MENU_CONTEXTS = "Definición de Contextos" 

router = APIRouter(
    prefix="/api/v1/admin/context-definitions",
    tags=["Admin - Context Definitions"]
)

@router.post(
    "/",
    response_model=ContextDefinitionResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create New Context Definition"
)
async def create_new_context_definition_endpoint(
    context_in: ContextDefinitionCreate,
    db: AsyncSession = Depends(get_crud_db_session),
    # Tu endpoint original parecía tener 'menu_name' como parámetro para el decorador.
    # Si `require_roles` espera `menu_name`, úsalo. Si espera una lista, usa la lista.
    # Voy a usar la versión más probable (lista de roles).
    current_user: AppUser = Depends(require_roles(ROLES_MANAGE_CONTEXTS))
):
    print(f"CONTEXT_DEF_API (Create): Admin '{current_user.username_ad}' creando contexto '{context_in.name}'.")

    existing_context = await crud_context_definition.get_context_definition_by_name(db, name=context_in.name)
    if existing_context:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe una Definición de Contexto con el nombre '{context_in.name}'."
        )
    
    # ... Tu lógica de validación (muy buena práctica) ...
    if context_in.main_type == ContextMainType.DOCUMENTAL:
        if context_in.processing_config_database_query is not None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Para main_type DOCUMENTAL, processing_config_database_query no debe ser provisto.")
    elif context_in.main_type == ContextMainType.DATABASE_QUERY:
        if context_in.processing_config_documental is not None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Para main_type DATABASE_QUERY, processing_config_documental no debe ser provisto.")
        if not context_in.db_connection_config_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Para main_type DATABASE_QUERY, se requiere un db_connection_config_id.")

    try:
        created_context = await crud_context_definition.create_context_definition(db=db, context_in=context_in)
        return created_context
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        print(f"ERROR en create_new_context_definition_endpoint: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al crear la definición de contexto.")

# ### [VERSIÓN CON DEPURACIÓN INTEGRADA] ###
# Esta es la función clave modificada para cazar el error.
@router.get("/", response_model=List[ContextDefinitionResponse], summary="Read All Context Definitions")
async def read_all_context_definitions_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=2000),
    main_type_filter: Optional[ContextMainType] = Query(None, alias="main_type", description="Filtrar por tipo principal de contexto."),
    is_active_filter: Optional[bool] = Query(None, alias="is_active", description="Filtrar por estado activo."),
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_VIEW)) 
):
    print(f"CONTEXT_DEF_API (List DEBUG MODE): Admin '{current_user.username_ad}' listando contextos.")
    
    # 1. Obtenemos los contextos de la DB (tu CRUD ya los prepara con relaciones)
    contexts = await crud_context_definition.get_context_definitions(db=db, skip=skip, limit=limit)
    
    # 2. Aplicamos filtros adicionales en Python, como ya lo hacías.
    filtered_contexts = contexts
    if main_type_filter is not None:
        # Importante: compara el valor del enum, no el enum en sí, si `main_type` es string en el modelo
        filtered_contexts = [ctx for ctx in filtered_contexts if ctx.main_type.value == main_type_filter.value]
    if is_active_filter is not None:
        filtered_contexts = [ctx for ctx in filtered_contexts if ctx.is_active == is_active_filter]
        
    # 3. Bucle de validación para encontrar el "culpable" que rompe Pydantic
    validated_response_list = []
    for db_context in filtered_contexts:
        try:
            # Intentamos validar cada objeto ORM individualmente.
            # Esta es la operación que FastAPI hace por debajo antes de enviar la respuesta.
            validated_item = ContextDefinitionResponse.model_validate(db_context)
            validated_response_list.append(validated_item)
        except ValidationError as e:
            # ¡BINGO! Si un contexto falla, este bloque se ejecuta.
            print("\n" + "="*80)
            print("!!! ERROR DE VALIDACIÓN DE PYDANTIC ENCONTRADO !!!")
            print(f"El objeto 'ContextDefinition' con ID: {getattr(db_context, 'id', 'ID Desconocido')} ha fallado la validación.")
            print(f"Nombre del Contexto: {getattr(db_context, 'name', 'Nombre Desconocido')}")
            print("\n--- DATOS CRUDOS del `processing_config` de la BD para este objeto:")
            print(json.dumps(getattr(db_context, 'processing_config', {}), indent=2))
            print("\n--- DETALLES DEL ERROR DE VALIDACIÓN DE PYDANTIC:")
            print(json.dumps(e.errors(), indent=2))
            print("="*80 + "\n")
            
            # Lanzamos una excepción HTTP clara para detener el proceso
            raise HTTPException(
                status_code=500, 
                detail=f"Error interno al validar los datos del Contexto ID={getattr(db_context, 'id', '???')}. "
                       f"Por favor, revisa los logs del servidor del backend para detalles específicos."
            )
            
    # 4. Si todos los contextos pasan la validación, devolvemos la lista.
    # El `response_model` se aplicará a los objetos originales del CRUD.
    return filtered_contexts


@router.get("/{context_id}", response_model=ContextDefinitionResponse, summary="Read Context Definition by ID")
async def read_context_definition_by_id_endpoint(
    context_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_CAN_VIEW))
):
    print(f"CONTEXT_DEF_API (Get ID): Admin '{current_user.username_ad}' obteniendo contexto ID: {context_id}.")
    db_context = await crud_context_definition.get_context_definition_by_id(db=db, context_id=context_id, load_relations_fully=True)
    if db_context is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Definición de Contexto no encontrada.")
    return db_context


@router.put("/{context_id}", response_model=ContextDefinitionResponse, summary="Update Existing Context Definition")
async def update_existing_context_definition_endpoint(
    context_id: int,
    context_update_in: ContextDefinitionUpdate,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_MANAGE_CONTEXTS))
):
    print(f"CONTEXT_DEF_API (Update): Admin '{current_user.username_ad}' actualizando contexto ID: {context_id}")

    db_context = await crud_context_definition.get_context_definition_by_id(db=db, context_id=context_id, load_relations_fully=False) # No necesita cargar todo
    if db_context is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Definición de Contexto no encontrada para actualizar.")
    
    # ... Tu lógica de validación ...
    if context_update_in.name and context_update_in.name != db_context.name:
        existing_name_context = await crud_context_definition.get_context_definition_by_name(db, name=context_update_in.name)
        if existing_name_context and existing_name_context.id != context_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Ya existe otra Definición de Contexto con el nombre '{context_update_in.name}'.")

    try:
        updated_context_obj = await crud_context_definition.update_context_definition(
            db=db, db_context_orm_obj=db_context, context_in=context_update_in
        )
        return updated_context_obj
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        print(f"ERROR en update_existing_context_definition_endpoint: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al actualizar la definición de contexto.")


@router.delete("/{context_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Context Definition")
async def delete_context_definition_endpoint(
    context_id: int,
    db: AsyncSession = Depends(get_crud_db_session),
    current_user: AppUser = Depends(require_roles(ROLES_MANAGE_CONTEXTS))
):
    print(f"CONTEXT_DEF_API (Delete): Admin '{current_user.username_ad}' eliminando contexto ID: {context_id}")
    
    deleted_context = await crud_context_definition.delete_context_definition(db=db, context_id=context_id)
    if deleted_context is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Definición de Contexto no encontrada para eliminar.")
    return None