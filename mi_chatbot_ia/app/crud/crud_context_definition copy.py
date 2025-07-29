# app/crud/crud_context_definition.py
import json
from typing import Optional, List, Any, Dict, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.context_definition import ContextDefinition as ContextDefModel, ContextMainType as SQLA_ContextMainType
from app.models.document_source_config import DocumentSourceConfig as DocSourceModel
# Importar los demás modelos SQLAlchemy si son necesarios para las relaciones
from app.models.db_connection_config import DatabaseConnectionConfig
from app.models.llm_model_config import LLMModelConfig
from app.models.virtual_agent_profile import VirtualAgentProfile

from app.schemas.schemas import (
    ContextDefinitionCreate, ContextDefinitionUpdate,
    DocumentalProcessingConfigSchema, DatabaseQueryProcessingConfigSchema
)


def _serialize_processing_config_to_json_for_db(
    context_input_schema: Union[ContextDefinitionCreate, ContextDefinitionUpdate],
    # El main_type efectivo se determina antes de llamar a esta función si es un Update.
    # Para Create, el context_input_schema.main_type es el definitivo.
    effective_main_type: SQLA_ContextMainType 
) -> Optional[Dict[str, Any]]:
    """
    Toma el schema de entrada y el tipo principal efectivo, extrae el processing_config apropiado,
    lo convierte a dict (JSON-serializable), y lo devuelve.
    """
    if effective_main_type == SQLA_ContextMainType.DOCUMENTAL:
        if context_input_schema.processing_config_documental:
            return context_input_schema.processing_config_documental.model_dump(mode='json', exclude_none=True)
    elif effective_main_type == SQLA_ContextMainType.DATABASE_QUERY:
        if context_input_schema.processing_config_database_query:
            return context_input_schema.processing_config_database_query.model_dump(mode='json', exclude_none=True)
    # Futuro: elif effective_main_type == SQLA_ContextMainType.IMAGE_ANALYSIS: ...
    return None


async def _prepare_context_definition_orm_for_response(
    db: AsyncSession, context_orm_obj: ContextDefModel
) -> ContextDefModel:
    """
    Prepara el objeto ContextDefModel ORM con atributos transitorios que coinciden con los
    `validation_alias` de ContextDefinitionResponse Pydantic schema.
    Modifica context_orm_obj in-place. Las relaciones principales deben estar
    pre-cargadas (con selectinload) antes de llamar a esta función.
    """
    
    # 1. Para raw_processing_config_from_db (validation_alias="processing_config")
    #    El modelo ORM ya tiene 'processing_config' como un dict.
    #    No es necesario hacer setattr si Pydantic puede leerlo directamente.
    #    Pero si el schema lo requiere explícitamente por el alias:
    if not hasattr(context_orm_obj, 'processing_config_alias_for_raw'): # Evitar re-asignar si se llama multiples veces
        setattr(context_orm_obj, 'processing_config', context_orm_obj.processing_config)


    # 2. Para processing_config_documental_parsed (validation_alias="processing_config_documental_from_db")
    #    y processing_config_database_query_parsed (validation_alias="processing_config_database_query_from_db")
    
    # Limpiar/inicializar los atributos transitorios esperados por Pydantic (validation_alias)
    setattr(context_orm_obj, 'processing_config_documental_from_db', None)
    setattr(context_orm_obj, 'processing_config_database_query_from_db', None)

    current_processing_config_dict = context_orm_obj.processing_config # Es un dict desde JSONB

    if current_processing_config_dict and isinstance(current_processing_config_dict, dict):
        try:
            if context_orm_obj.main_type == SQLA_ContextMainType.DOCUMENTAL:
                parsed_doc_config = DocumentalProcessingConfigSchema.model_validate(current_processing_config_dict)
                setattr(context_orm_obj, 'processing_config_documental_from_db', parsed_doc_config)
            elif context_orm_obj.main_type == SQLA_ContextMainType.DATABASE_QUERY:
                parsed_db_config = DatabaseQueryProcessingConfigSchema.model_validate(current_processing_config_dict)
                setattr(context_orm_obj, 'processing_config_database_query_from_db', parsed_db_config)
            # Futuro: elif para IMAGE_ANALYSIS
        except Exception as e_parse_config:
            print(f"CRUD WARNING: Context ID {context_orm_obj.id} - No se pudo validar "
                  f"processing_config para main_type '{context_orm_obj.main_type.value}': {e_parse_config}")
            # Los atributos '..._from_db' quedarán como None, y Pydantic manejará el Optional.

    # Las relaciones (document_sources, db_connection, etc.) deben ser cargadas por el llamador
    # usando selectinload, y Pydantic las tomará directamente.
    return context_orm_obj


async def create_context_definition(db: AsyncSession, context_in: ContextDefinitionCreate) -> ContextDefModel:
    processing_config_for_db = _serialize_processing_config_to_json_for_db(
        context_in, context_in.main_type # El main_type del create schema es el definitivo
    )

    db_context_data = {
        "name": context_in.name,
        "description": context_in.description,
        "is_active": context_in.is_active,
        "main_type": context_in.main_type.value, # Pydantic enum se convierte a string para SAEnum
        "processing_config": processing_config_for_db,
        "default_llm_model_config_id": context_in.default_llm_model_config_id,
        "virtual_agent_profile_id": context_in.virtual_agent_profile_id
    }
    if context_in.main_type == ContextMainType.DATABASE_QUERY: # Usar el Pydantic enum para comparar
        db_context_data["db_connection_config_id"] = context_in.db_connection_config_id
    
    db_context = ContextDefModel(**db_context_data)

    if context_in.document_source_ids:
        # Esta es una forma más segura de cargar, asegurando que no se mezclen sesiones si db fuera diferente.
        docs_to_link = await db.execute(
            select(DocSourceModel).filter(DocSourceModel.id.in_(context_in.document_source_ids))
        )
        db_context.document_sources.extend(docs_to_link.scalars().all())

    db.add(db_context)
    await db.commit()
    # No es necesario refresh para las M-M si se usa 'extend' antes del commit.
    # Refresh para obtener ID y timestamps es buena idea.
    await db.refresh(db_context) 
    # Cargar las relaciones FK para que el objeto retornado las tenga
    await db.refresh(db_context, attribute_names=['default_llm_model_config', 'virtual_agent_profile', 'db_connection_config'])


    # get_by_id ahora se encarga de llamar a _prepare... y cargar M-M también
    return await get_context_definition_by_id(db, db_context.id, load_relations_fully=True)


async def get_context_definition_by_id(db: AsyncSession, context_id: int, load_relations_fully: bool = True) -> Optional[ContextDefModel]:
    stmt = select(ContextDefModel).filter(ContextDefModel.id == context_id)
    if load_relations_fully:
        stmt = stmt.options(
            selectinload(ContextDefModel.document_sources),
            selectinload(ContextDefModel.db_connection_config), 
            selectinload(ContextDefModel.default_llm_model_config),
            selectinload(ContextDefModel.virtual_agent_profile)
        )
    result = await db.execute(stmt)
    db_context = result.scalars().one_or_none() # Use one_or_none para claridad
    
    if db_context:
        return await _prepare_context_definition_orm_for_response(db, db_context)
    return None

async def get_context_definition_by_name(db: AsyncSession, name: str, load_relations_fully: bool = True) -> Optional[ContextDefModel]:
    stmt = select(ContextDefModel).filter(ContextDefModel.name == name)
    if load_relations_fully:
         stmt = stmt.options(
            selectinload(ContextDefModel.document_sources),
            selectinload(ContextDefModel.db_connection_config),
            selectinload(ContextDefModel.default_llm_model_config),
            selectinload(ContextDefModel.virtual_agent_profile)
        )
    result = await db.execute(stmt)
    db_context = result.scalars().one_or_none()

    if db_context:
        return await _prepare_context_definition_orm_for_response(db, db_context)
    return None
    
async def get_context_definitions(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[ContextDefModel]:
    stmt = select(ContextDefModel).offset(skip).limit(limit).order_by(ContextDefModel.name).options(
        selectinload(ContextDefModel.document_sources),
        selectinload(ContextDefModel.db_connection_config),
        selectinload(ContextDefModel.default_llm_model_config),
        selectinload(ContextDefModel.virtual_agent_profile)
    )
    result = await db.execute(stmt)
    contexts_orm_list = result.scalars().unique().all() # unique() es importante con selectinload M-M
    
    prepared_contexts = []
    for ctx_orm in contexts_orm_list:
        prepared_contexts.append(await _prepare_context_definition_orm_for_response(db, ctx_orm))
    return prepared_contexts


async def update_context_definition(
    db: AsyncSession, 
    db_context_orm_obj: ContextDefModel, # Objeto ORM a actualizar
    context_in: ContextDefinitionUpdate    # Datos de entrada Pydantic
) -> ContextDefModel:
    
    update_data_dict = context_in.model_dump(exclude_unset=True)
    
    # Determinar el main_type efectivo para el config
    effective_main_type = db_context_orm_obj.main_type
    if "main_type" in update_data_dict and update_data_dict["main_type"] is not None:
        effective_main_type = update_data_dict["main_type"]

    # Actualizar campos simples del modelo ORM
    for field_name, value in update_data_dict.items():
        if field_name not in {"document_source_ids", "processing_config_documental", "processing_config_database_query"}:
            setattr(db_context_orm_obj, field_name, value)

    # Actualizar processing_config JSON
    # Si CUALQUIERA de los configs estructurados está en el input, regeneramos el JSON para la BD.
    # Esto incluye el caso donde se envía explícitamente `None` para un config (para limpiarlo).
    if context_in.model_fields_set.intersection({'processing_config_documental', 'processing_config_database_query'}):
        # Usamos el context_in completo para _serialize, ya que tiene los campos de config
        db_context_orm_obj.processing_config = _serialize_processing_config_to_json_for_db(context_in, effective_main_type)

    # Actualizar relación M-M document_sources
    if context_in.document_source_ids is not None: # [] significa limpiar, si es None, no se toca.
        # Para actualizar relaciones M-M, es más seguro limpiar y re-añadir.
        db_context_orm_obj.document_sources.clear() 
        if context_in.document_source_ids: # Si no es una lista vacía
            docs_to_link = await db.execute(
                select(DocSourceModel).filter(DocSourceModel.id.in_(context_in.document_source_ids))
            )
            db_context_orm_obj.document_sources.extend(docs_to_link.scalars().all())
            
    # db.add(db_context_orm_obj) # SQLAlchemy maneja objetos en sesión
    await db.commit()
    
    # Devolver el objeto completamente poblado y refrescado
    # Cuidado con las relaciones si no se cargan en el refresh aquí.
    # Es mejor llamar a get_by_id que ya maneja el selectinload y _prepare
    refreshed_and_prepared_obj = await get_context_definition_by_id(db, db_context_orm_obj.id, load_relations_fully=True)
    if refreshed_and_prepared_obj is None: # Poco probable si acabamos de hacer commit
        raise Exception("Error al refrescar ContextDefinition después de update.")
    return refreshed_and_prepared_obj

async def delete_context_definition(db: AsyncSession, context_id: int) -> Optional[ContextDefModel]:
    db_context_obj = await db.get(ContextDefModel, context_id)
    if db_context_obj:
        await db.delete(db_context_obj)
        await db.commit()
        return db_context_obj # Retorna el objeto borrado (ya no estará "preparado")
    return None