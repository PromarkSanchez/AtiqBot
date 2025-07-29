import json
from typing import Optional, List, Any, Dict, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, joinedload # Aseguramos que joinedload esté importado

from app.models.context_definition import ContextDefinition as ContextDefModel
from app.models.context_definition import ContextMainType as SQLA_ContextMainType # Renombrado para claridad
from app.models.document_source_config import DocumentSourceConfig as DocSourceModel
# Importamos los modelos necesarios para las relaciones anidadas
from app.models.virtual_agent_profile import VirtualAgentProfile
from app.models.llm_model_config import LLMModelConfig

from app.schemas.schemas import (
    ContextDefinitionCreate, ContextDefinitionUpdate,
    DocumentalProcessingConfigSchema, DatabaseQueryProcessingConfigSchema
)
 
def _serialize_processing_config_to_json_for_db(
    context_input_schema: Union[ContextDefinitionCreate, ContextDefinitionUpdate],
    effective_main_type: SQLA_ContextMainType
) -> Optional[Dict[str, Any]]:
    
    config_to_serialize = None
    if effective_main_type == SQLA_ContextMainType.DOCUMENTAL:
        if context_input_schema.processing_config_documental:
            config_to_serialize = context_input_schema.processing_config_documental
    elif effective_main_type == SQLA_ContextMainType.DATABASE_QUERY:
        if context_input_schema.processing_config_database_query:
            config_to_serialize = context_input_schema.processing_config_database_query

    if not config_to_serialize:
        return None

    db_json_dict = config_to_serialize.model_dump(mode='json', exclude_none=True)

    if effective_main_type == SQLA_ContextMainType.DATABASE_QUERY and \
       "sql_select_policy" in db_json_dict and \
       isinstance(db_json_dict["sql_select_policy"], dict) and \
       "column_access_rules" in db_json_dict["sql_select_policy"] and \
       isinstance(db_json_dict["sql_select_policy"]["column_access_rules"], list):
        
        rules_list = db_json_dict["sql_select_policy"].pop("column_access_rules")
        policy_dict_for_db = {}
        for rule_item in rules_list:
            if isinstance(rule_item, dict) and "table_name" in rule_item and "column_policy" in rule_item:
                policy_content = rule_item["column_policy"]
                if hasattr(policy_content, 'model_dump'):
                    policy_dict_for_db[rule_item["table_name"]] = policy_content.model_dump(mode='json', exclude_none=True)
                elif isinstance(policy_content, dict):
                    policy_dict_for_db[rule_item["table_name"]] = policy_content
                else:
                    policy_dict_for_db[rule_item["table_name"]] = None
        db_json_dict["sql_select_policy"]["column_access_policy"] = policy_dict_for_db

    return db_json_dict

async def _prepare_context_definition_orm_for_response(
    db: AsyncSession, context_orm_obj: ContextDefModel
) -> ContextDefModel:
    setattr(context_orm_obj, 'processing_config_documental_from_db', None)
    setattr(context_orm_obj, 'processing_config_database_query_from_db', None)

    current_processing_config_dict = context_orm_obj.processing_config

    if current_processing_config_dict and isinstance(current_processing_config_dict, dict):
        try:
            if context_orm_obj.main_type == SQLA_ContextMainType.DOCUMENTAL:
                parsed_doc_config = DocumentalProcessingConfigSchema.model_validate(current_processing_config_dict)
                setattr(context_orm_obj, 'processing_config_documental_from_db', parsed_doc_config)
            elif context_orm_obj.main_type == SQLA_ContextMainType.DATABASE_QUERY:
                parsed_db_config = DatabaseQueryProcessingConfigSchema.model_validate(current_processing_config_dict)
                setattr(context_orm_obj, 'processing_config_database_query_from_db', parsed_db_config)
        except Exception as e_parse_config:
            print(f"CRUD WARNING: Context ID {context_orm_obj.id} - Could not validate processing_config for main_type '{context_orm_obj.main_type.value}': {e_parse_config}")
    return context_orm_obj

async def create_context_definition(db: AsyncSession, context_in: ContextDefinitionCreate) -> ContextDefModel:
    processing_config_for_db = _serialize_processing_config_to_json_for_db(
        context_in, context_in.main_type
    )

    db_context_data = {
        "name": context_in.name,
        "description": context_in.description,
        "is_active": context_in.is_active,
        "is_public": context_in.is_public, # <--- AÑADIR ESTA LÍNEA
        "main_type": context_in.main_type, # El schema ya tiene el enum correcto
        "processing_config": processing_config_for_db,
        "default_llm_model_config_id": context_in.default_llm_model_config_id,
        "virtual_agent_profile_id": context_in.virtual_agent_profile_id,
        "db_connection_config_id": context_in.db_connection_config_id
    }
    
    db_context = ContextDefModel(**{k: v for k, v in db_context_data.items() if v is not None})

    if context_in.document_source_ids:
        docs_to_link = await db.execute(
            select(DocSourceModel).filter(DocSourceModel.id.in_(context_in.document_source_ids))
        )
        db_context.document_sources.extend(docs_to_link.scalars().all())

    db.add(db_context)
    await db.commit()
    await db.refresh(db_context)
    
    return await get_context_definition_by_id(db, db_context.id, load_relations_fully=True)


# ### [CORRECCIÓN APLICADA AQUÍ] ###
async def get_context_definition_by_id(db: AsyncSession, context_id: int, load_relations_fully: bool = True) -> Optional[ContextDefModel]:
    stmt = select(ContextDefModel).filter(ContextDefModel.id == context_id)
    if load_relations_fully:
        stmt = stmt.options(
            selectinload(ContextDefModel.document_sources),
            selectinload(ContextDefModel.db_connection_config), 
            selectinload(ContextDefModel.default_llm_model_config),
            # Carga ansiosa de la relación anidada para evitar errores de Lazy Load
            joinedload(ContextDefModel.virtual_agent_profile).joinedload(VirtualAgentProfile.llm_model_config)
        )
    result = await db.execute(stmt)
    db_context = result.scalars().one_or_none()
    
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
            # Aplicamos la misma corrección aquí para consistencia
            joinedload(ContextDefModel.virtual_agent_profile).joinedload(VirtualAgentProfile.llm_model_config)
        )
    result = await db.execute(stmt)
    db_context = result.scalars().one_or_none()

    if db_context:
        return await _prepare_context_definition_orm_for_response(db, db_context)
    return None

# ### [CORRECCIÓN APLICADA AQUÍ] ###
async def get_context_definitions(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[ContextDefModel]:
    stmt = (
        select(ContextDefModel)
        .offset(skip)
        .limit(limit)
        .order_by(ContextDefModel.name)
        .options(
            # Cargamos todas las relaciones directas
            selectinload(ContextDefModel.document_sources),
            selectinload(ContextDefModel.db_connection_config),
            selectinload(ContextDefModel.default_llm_model_config),
            
            # Y la relación anidada crucial que causaba el error de Lazy Load
            joinedload(ContextDefModel.virtual_agent_profile).joinedload(VirtualAgentProfile.llm_model_config)
        )
    )
    result = await db.execute(stmt)
    contexts_orm_list = result.scalars().unique().all()
    
    prepared_contexts = []
    for ctx_orm in contexts_orm_list:
        prepared_contexts.append(await _prepare_context_definition_orm_for_response(db, ctx_orm))
    return prepared_contexts

async def update_context_definition(
    db: AsyncSession, 
    db_context_orm_obj: ContextDefModel,
    context_in: ContextDefinitionUpdate
) -> ContextDefModel:
    
    update_data_dict = context_in.model_dump(exclude_unset=True)
    
    effective_main_type = db_context_orm_obj.main_type
    if "main_type" in update_data_dict and update_data_dict["main_type"] is not None:
        effective_main_type = update_data_dict["main_type"]

    for field_name, value in update_data_dict.items():
        if field_name not in {"document_source_ids", "processing_config_documental", "processing_config_database_query"}:
            setattr(db_context_orm_obj, field_name, value)

    if context_in.model_fields_set.intersection({'processing_config_documental', 'processing_config_database_query'}):
        db_context_orm_obj.processing_config = _serialize_processing_config_to_json_for_db(context_in, effective_main_type)

    if context_in.document_source_ids is not None:
        db_context_orm_obj.document_sources.clear() 
        if context_in.document_source_ids:
            docs_to_link = await db.execute(
                select(DocSourceModel).filter(DocSourceModel.id.in_(context_in.document_source_ids))
            )
            db_context_orm_obj.document_sources.extend(docs_to_link.scalars().all())
            
    await db.commit()
    
    refreshed_and_prepared_obj = await get_context_definition_by_id(db, db_context_orm_obj.id, load_relations_fully=True)
    if refreshed_and_prepared_obj is None:
        raise Exception("Error al refrescar ContextDefinition después de update.")
    return refreshed_and_prepared_obj

async def delete_context_definition(db: AsyncSession, context_id: int) -> Optional[ContextDefModel]:
    db_context_obj = await db.get(ContextDefModel, context_id)
    if db_context_obj:
        await db.delete(db_context_obj)
        await db.commit()
        return db_context_obj
    return None