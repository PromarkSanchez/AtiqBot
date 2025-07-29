// src/components/admin/context-definitions/ContextDefinitionForm.tsx

import React, { useEffect, useMemo, useState } from 'react';
import { useForm, Controller, type SubmitHandler, useFieldArray, type Control, type UseFormRegister } from 'react-hook-form';
import { Link } from 'react-router-dom';
import toast, { Toaster } from 'react-hot-toast';

// --- IMPORTS DE SERVICIOS Y TIPOS ---
import {
  useReadAllDocumentSourcesApiV1AdminDocSourcesGet,
  useReadAllDbConnectionsApiV1AdminDbConnectionsGet,
  useReadAllLlmModelConfigsApiV1AdminLlmModelsGet,
  useReadAllVirtualAgentProfilesApiV1AdminVirtualAgentProfilesGet,
  useInspectDbConnectionEndpointApiV1AdminDbConnectionsConnIdInspectGet,
} from '../../../services/api/endpoints';
import type {
  ContextDefinitionCreate,
  ContextDefinitionUpdate,
  ContextDefinitionResponse,
  DocumentalProcessingConfigSchema,
  DatabaseQueryProcessingConfigSchemaOutput as ApiDatabaseQueryProcessingConfigSchemaOutput,
  SqlSelectPolicySchema as ApiSqlSelectPolicyOutput,
  SqlTableAccessRuleSchema,
  StoredProcedureTool as ApiStoredProcedureTool,
} from '../../../services/api/schemas';
import { ContextMainType, ParamTransformType } from '../../../services/api/schemas';

// --- IMPORTS DE COMPONENTES E ICONOS ---
import CreatableMultiSelect from '../../shared/forms/CreatableMultiSelect';
import { Button, IconButton } from '../../shared/Button';
import { PlusCircleIcon, TrashIcon, InformationCircleIcon, ChevronDownIcon, ChevronUpIcon, DocumentTextIcon, CommandLineIcon, ArrowPathIcon } from '@heroicons/react/24/outline';


// --- DEFINICIONES DE TIPOS Y DEFAULTS PARA EL FORMULARIO ---

// Helper deepCopy
const deepCopy = <T,>(obj: T): T => JSON.parse(JSON.stringify(obj));

// Tipos internos del formulario para manejar SPs, Parámetros y Políticas SQL
type FormSPParameter = {
    name: string;
    description_for_llm: string;
    is_required: boolean; // <-- AÑADE ESTA LÍNEA
    clarification_question: string; // <-- AÑADE ESTA LÍNEA (la haremos un string simple, no opcional)
};

type FormStoredProcedureTool = { id?: string; tool_name: string; procedure_name: string; description_for_llm: string; parameters: FormSPParameter[]; };
type FormSqlColumnPolicy = { allowed_columns: string[]; forbidden_columns: string[]; };
type FormSqlTableRule = { id?: string; table_name: string; column_policy: FormSqlColumnPolicy; };
type FormSqlSelectPolicy = Omit<ApiSqlSelectPolicyOutput, 'column_access_rules' | 'column_access_policy_from_db' | 'allowed_tables_for_select'> & { column_access_rules: FormSqlTableRule[]; };

// Tipo principal para la configuración de DB_QUERY dentro del formulario
type FormProcessingConfigDBQuery = Omit<ApiDatabaseQueryProcessingConfigSchemaOutput, 'custom_table_descriptions' | 'sql_select_policy' | 'selected_schema_tables_for_llm' | 'tools'> & {
  selected_schema_tables_for_llm: string[];
  custom_table_descriptions_json: string;
  sql_select_policy: FormSqlSelectPolicy;
  tools: FormStoredProcedureTool[];
};

// El tipo completo que representa todos los campos del formulario
type FormValues = {
  name: string;
  description: string | null;
  is_active: boolean;
  is_public: boolean;
  main_type: ContextMainType | '';
  default_llm_model_config_id: string;
  virtual_agent_profile_id: string;
  document_source_ids: number[];
  db_connection_config_id: string;
  processing_config_documental: DocumentalProcessingConfigSchema;
  processing_config_database_query: FormProcessingConfigDBQuery;
};

// Valores por defecto para cada parte del formulario
const defaultSPParameterValues: FormSPParameter = {
    name: '',
    description_for_llm: '',
    is_required: true, 
    clarification_question: '',  
};

const defaultStoredProcedureToolValues: FormStoredProcedureTool = { tool_name: '', procedure_name: '', description_for_llm: '', parameters: [] };
const defaultDocConfigValues: DocumentalProcessingConfigSchema = { chunk_size: 1000, chunk_overlap: 200 };
const defaultFormSqlSelectPolicy: FormSqlSelectPolicy = {
    default_select_limit: 10, max_select_limit: 50, allow_joins: true,
    allowed_join_types: ["INNER", "LEFT"], allow_aggregations: true,
    allowed_aggregation_functions: ["COUNT", "SUM", "AVG", "MIN", "MAX"],
    allow_group_by: true, allow_order_by: true, allow_where_clauses: true,
    forbidden_keywords_in_where: ["DELETE", "UPDATE", "INSERT", "DROP"],
    column_access_rules: [], llm_instructions_for_select: [],
};
const defaultDbQueryConfigValues: FormProcessingConfigDBQuery = {
  schema_info_type: "dictionary_table_sqlserver_custom", dictionary_table_query: '',
  selected_schema_tables_for_llm: [], custom_table_descriptions_json: '{}',
  db_schema_chunk_size: 2000, db_schema_chunk_overlap: 200,
  sql_select_policy: deepCopy(defaultFormSqlSelectPolicy),
  tools: [],
};
const defaultFormValues: FormValues = {
    name: '',
    description: null,
    is_active: true,
    is_public: true,
    main_type: '',
    default_llm_model_config_id: '',
    virtual_agent_profile_id: '',
    document_source_ids: [],
    db_connection_config_id: '',
    processing_config_documental: deepCopy(defaultDocConfigValues),
    processing_config_database_query: deepCopy(defaultDbQueryConfigValues),
};
const mainTypeOptions = [
  { value: ContextMainType.DOCUMENTAL, label: 'Contenido Documental', icon: DocumentTextIcon },
  { value: ContextMainType.DATABASE_QUERY, label: 'Consulta a BD', icon: CommandLineIcon },
];

interface ContextDefinitionFormProps {
  initialData?: ContextDefinitionResponse | null;
  onSubmit: (data: ContextDefinitionCreate | ContextDefinitionUpdate, isEditMode: boolean) => Promise<void>;
  onCancel: () => void;
  isSubmittingGlobal: boolean;
  isEditMode: boolean;
}
    const labelClass = "block text-xs font-medium text-gray-600 dark:text-gray-400";
    const inputClass = "block w-full mt-1 text-sm rounded-md shadow-sm dark:bg-slate-900 dark:text-white dark:border-slate-700";
    const checkboxLabelClass = "flex items-center text-sm text-gray-700 dark:text-gray-300 select-none";
    const checkboxClass = "h-4 w-4 rounded dark:bg-slate-800 dark:border-slate-600";
    
// --- SUB-COMPONENTE PARA LOS PARÁMETROS DE UNA HERRAMIENTA ---
const ToolParametersControl: React.FC<{ toolIndex: number; control: Control<FormValues>; register: UseFormRegister<FormValues> }> = ({ toolIndex, control, register }) => {
    const { fields, append, remove } = useFieldArray({ control, name: `processing_config_database_query.tools.${toolIndex}.parameters` });
    return (
        <div className="pl-4 border-l-2 border-slate-200 dark:border-slate-700 space-y-3">
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Parámetros de la Herramienta</h4>
            {fields.map((item, paramIndex) => (
                <div key={item.id} className="p-3 bg-slate-50 dark:bg-slate-700/50 rounded-md space-y-2 relative">
                    <IconButton type="button" icon={<TrashIcon className="h-4 w-4"/>} onClick={() => remove(paramIndex)} variant="ghost" aria-label="Eliminar Parámetro" className="absolute top-1 right-1 !p-1 text-gray-500 hover:text-red-500"/>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                            <label htmlFor={`param_name_${toolIndex}_${paramIndex}`} className={labelClass}>Nombre del Parámetro (en BD)</label>
                            <input id={`param_name_${toolIndex}_${paramIndex}`} {...register(`processing_config_database_query.tools.${toolIndex}.parameters.${paramIndex}.name`)} placeholder="ej: p_ndoc_identidad" className={inputClass} />
                        </div>
                        <div className="self-end pb-1">
                            <Controller
                                name={`processing_config_database_query.tools.${toolIndex}.parameters.${paramIndex}.is_required`}
                                control={control}
                                render={({ field }) => (
                                    <label htmlFor={`param_req_${toolIndex}_${paramIndex}`} className={checkboxLabelClass}>
                                        <input id={`param_req_${toolIndex}_${paramIndex}`} type="checkbox" checked={field.value} onChange={field.onChange} className={checkboxClass} />
                                        <span className="ml-2">Es Requerido</span>
                                    </label>
                                )}
                            />
                        </div>
                    </div>
                    <div>
                        <label htmlFor={`param_desc_${toolIndex}_${paramIndex}`} className={labelClass}>Descripción (para el LLM)</label>
                        <input id={`param_desc_${toolIndex}_${paramIndex}`} {...register(`processing_config_database_query.tools.${toolIndex}.parameters.${paramIndex}.description_for_llm`)} placeholder="ej: DNI del usuario" className={inputClass} />
                    </div>
                    <div>
                        <label htmlFor={`param_clarify_${toolIndex}_${paramIndex}`} className={labelClass}>Pregunta de Clarificación (si falta y es requerido)</label>
                        <input id={`param_clarify_${toolIndex}_${paramIndex}`} {...register(`processing_config_database_query.tools.${toolIndex}.parameters.${paramIndex}.clarification_question`)} placeholder="ej: ¿Cuál es el código de tu carrera?" className={inputClass} />
                    </div>
                </div>
            ))}
            <Button type="button" size="md" variant="ghost" onClick={() => append(defaultSPParameterValues)} className="!p-0 text-indigo-600 dark:text-indigo-400">
                + Añadir Parámetro
            </Button>
        </div>
    );
};
// --- COMPONENTE PRINCIPAL DEL FORMULARIO ---
  const ContextDefinitionForm: React.FC<ContextDefinitionFormProps> = ({ initialData, onSubmit, onCancel, isSubmittingGlobal, isEditMode }) => {
  const rhfMethods = useForm<FormValues>({ mode: 'onChange', defaultValues: deepCopy(defaultFormValues) });
  const { register, handleSubmit, reset, control, watch, setValue, getValues, trigger, formState: { errors, isDirty, isValid: isFormValid }, } = rhfMethods;



  const currentMainType = watch('main_type');
  const watchedDbConnectionId = watch('db_connection_config_id');
  const [isSqlPolicyExpanded, setIsSqlPolicyExpanded] = useState(false);
  
  // Lógica de Inspección de BD (con carga manual por botón)
  const numericDbConnId = watchedDbConnectionId ? parseInt(watchedDbConnectionId, 10) : null;
  const { data: dbInspectionData, isLoading: isLoadingDbTables, isError: isErrorDbTables, refetch: inspectDatabase } = 
    useInspectDbConnectionEndpointApiV1AdminDbConnectionsConnIdInspectGet(
      numericDbConnId!, { query: { enabled: false, queryKey: ['dbInspection', numericDbConnId] } }
    );
  
  const handleInspectClick = () => {
    if (numericDbConnId) {
      toast.promise(inspectDatabase(), {
         loading: 'Inspeccionando base de datos...',
         success: (result: any) => `Inspección OK. Se encontraron ${result.data.tables.length} tablas.`, // Axios anida datos en 'data'
         error: 'Error al inspeccionar la BD.',
      });
    }
  };

  const dbSchemaTableOptions = useMemo(() => {
    if (!dbInspectionData) return [];
    return dbInspectionData.tables.map(table => ({ label: table.full_name, value: table.full_name }));
  }, [dbInspectionData]);

  // Hooks de datos para los selectores
  const commonQueryOptions = { query: { staleTime: 5 * 60 * 1000 } };
  const { data: docSourcesData, isLoading: isLoadingDocSources } = useReadAllDocumentSourcesApiV1AdminDocSourcesGet({ limit: 1000 }, { ...commonQueryOptions, query: { enabled: currentMainType === ContextMainType.DOCUMENTAL } });
  const availableDocSources = useMemo(() => (docSourcesData ?? []).map(ds => ({ value: ds.id, label: `${ds.name} (${ds.source_type})`})), [docSourcesData]);
  const { data: dbConnectionsData } = useReadAllDbConnectionsApiV1AdminDbConnectionsGet({ limit: 500 }, { ...commonQueryOptions, query: { enabled: currentMainType === ContextMainType.DATABASE_QUERY } });
  const availableDbConnections = useMemo(() => (dbConnectionsData ?? []).map(c => ({ value: c.id, label: `${c.name} (${c.db_type})`})), [dbConnectionsData]);
  const { data: llmModelsData } = useReadAllLlmModelConfigsApiV1AdminLlmModelsGet({ limit: 500 }, { ...commonQueryOptions, query: { enabled: !!currentMainType }});
  const availableLLMs = useMemo(() => (llmModelsData ?? []).map(llm => ({ value: llm.id, label: `${llm.display_name} (${llm.provider})` })), [llmModelsData]);
  const { data: vapsData } = useReadAllVirtualAgentProfilesApiV1AdminVirtualAgentProfilesGet({ limit: 500 }, { ...commonQueryOptions, query: { enabled: !!currentMainType }});
  const availableVAPs = useMemo(() => (vapsData ?? []).map(vap => ({ value: vap.id, label: vap.name })), [vapsData]);

  // useFieldArrays para las partes dinámicas del formulario
  const { fields: toolFields, append: appendTool, remove: removeTool } = useFieldArray({ control, name: "processing_config_database_query.tools" });
  const addToolItem = () => appendTool(deepCopy(defaultStoredProcedureToolValues));
  const { fields: ruleFields, append: appendRule, remove: removeRule } = useFieldArray({ control, name: "processing_config_database_query.sql_select_policy.column_access_rules" });
    const { fields: columnAccessRulesFields, append: appendCAR, remove: removeCAR } = useFieldArray({
      control, name: "processing_config_database_query.sql_select_policy.column_access_rules", keyName: "id"
    });
  const addColumnAccessRuleItem = () => appendRule(deepCopy({table_name: '', column_policy: { allowed_columns: [], forbidden_columns: [] }}));

  // Lógica de inicialización del formulario
  useEffect(() => {
    if (isEditMode && initialData) {
      const pConfigDb = initialData.processing_config_database_query;
      const valuesToSet: FormValues = {
        name: initialData.name,
        description: initialData.description ?? null,
        is_active: initialData.is_active ?? false,
        is_public: initialData.is_public  ?? false,
        main_type: initialData.main_type,
        default_llm_model_config_id: String(initialData.default_llm_model_config_id ?? ''),
        virtual_agent_profile_id: String(initialData.virtual_agent_profile_id ?? ''),
        document_source_ids: initialData.document_sources?.map(ds => ds.id) ?? [],
        db_connection_config_id: String(initialData.db_connection_config?.id ?? ''),
        processing_config_documental: initialData.processing_config_documental ? { ...defaultDocConfigValues, ...initialData.processing_config_documental } : deepCopy(defaultDocConfigValues),
        processing_config_database_query: pConfigDb ? {
          ...deepCopy(defaultDbQueryConfigValues),
          ...pConfigDb,
          custom_table_descriptions_json: JSON.stringify(pConfigDb.custom_table_descriptions || {}, null, 2),
          tools: (pConfigDb.tools as ApiStoredProcedureTool[] ?? []).map(t => ({ 
              ...t, 
              parameters: (t.parameters ?? []).map(p => ({
                  name: p.name,
                  description_for_llm: p.description_for_llm,
                  // Proporciona valores por defecto si no vienen de la API
                  is_required: p.is_required ?? true, 
                  clarification_question: p.clarification_question ?? ''
              }))
          })),          
          sql_select_policy: pConfigDb.sql_select_policy ? {
             ...deepCopy(defaultFormSqlSelectPolicy),
             ...pConfigDb.sql_select_policy,
             column_access_rules: (pConfigDb.sql_select_policy.column_access_rules as SqlTableAccessRuleSchema[] ?? []).map(r => ({
               table_name: r.table_name,
               column_policy: {
                 allowed_columns: r.column_policy?.allowed_columns || [],
                 forbidden_columns: r.column_policy?.forbidden_columns || [],
               },
             }))
          } : deepCopy(defaultFormSqlSelectPolicy),
        } : deepCopy(defaultDbQueryConfigValues),
      };
      reset(valuesToSet);
    } else {
      reset(deepCopy(defaultFormValues));
    }
  }, [initialData, isEditMode, reset]);
  
  // Lógica de envío del formulario
  const processFormSubmit: SubmitHandler<FormValues> = async (formData) => {
    console.log("FORM_SUBMIT: Datos crudos del formulario (FormValues):", deepCopy(formData));
    

    let procConfigDocPayload: DocumentalProcessingConfigSchema | undefined = undefined;
    let procConfigDbQueryPayloadForApi: ApiDatabaseQueryProcessingConfigSchemaOutput | undefined;
    
      // --- INICIO DEL PARCHE DE PRUEBA ---
    if (procConfigDbQueryPayloadForApi && procConfigDbQueryPayloadForApi.tools) {
        for (const tool of procConfigDbQueryPayloadForApi.tools) {
            // Buscamos nuestra herramienta de notas específica
            if (tool.tool_name === "fn_app_obtener_notas_curso") {
                for (const param of tool.parameters ?? []) {
                    // Si encontramos el parámetro del periodo, le añadimos la transformación
                    if (param.name === "p_speriodo") {
                        console.log("!!! DEBUG: Inyectando transformación REMOVE_DASHES para p_speriodo !!!");
                        // Asignamos el enum `ParamTransformType` que viene de los schemas
                        param.transformations = [ParamTransformType.REMOVE_DASHES]; 
                    }
                }
            }
        }
    }
    // --- FIN DEL PARCHE DE PRUEBA ---
    // Lógica para tipo DOCUMENTAL
    if (formData.main_type === ContextMainType.DOCUMENTAL) {
      procConfigDocPayload = {
        chunk_size: Number(formData.processing_config_documental.chunk_size),
        chunk_overlap: Number(formData.processing_config_documental.chunk_overlap),
      };
    } 
    // Lógica para tipo DATABASE_QUERY
    else if (formData.main_type === ContextMainType.DATABASE_QUERY) {
      let customDescs: Record<string, string> = {};
      try {
        customDescs = JSON.parse(formData.processing_config_database_query.custom_table_descriptions_json || '{}');
      } catch (e) {
        toast.error("El JSON de descripciones personalizadas es inválido.");
        return;
      }
      
      procConfigDbQueryPayloadForApi = {
        // Mapeamos los campos del formulario al schema que espera la API
        schema_info_type: formData.processing_config_database_query.schema_info_type,
        dictionary_table_query: formData.processing_config_database_query.dictionary_table_query,
        selected_schema_tables_for_llm: formData.processing_config_database_query.selected_schema_tables_for_llm || [],
        custom_table_descriptions: customDescs,
        db_schema_chunk_size: Number(formData.processing_config_database_query.db_schema_chunk_size),
        db_schema_chunk_overlap: Number(formData.processing_config_database_query.db_schema_chunk_overlap),
        
        // Mapeamos las herramientas (tools) al formato de la API
          tools: (formData.processing_config_database_query.tools || []).map(tool => ({
          tool_name: tool.tool_name,
          procedure_name: tool.procedure_name,
          description_for_llm: tool.description_for_llm,
          parameters: (tool.parameters || []).filter(p => p.name && p.description_for_llm), // Filtramos params vacíos
        })),
        
        // Mapeamos la política de SQL (se mantiene como antes)
        sql_select_policy: {
            ...formData.processing_config_database_query.sql_select_policy,
            allowed_tables_for_select: formData.processing_config_database_query.selected_schema_tables_for_llm || [],
        } as ApiSqlSelectPolicyOutput
      };
    }

    const baseSubmitPayload = {
      name: formData.name.trim(),
      description: formData.description?.trim() || null,
      is_active: formData.is_active,
      is_public: formData.is_public,
      default_llm_model_config_id: formData.default_llm_model_config_id ? parseInt(formData.default_llm_model_config_id) : undefined,
      virtual_agent_profile_id: formData.virtual_agent_profile_id ? parseInt(formData.virtual_agent_profile_id) : undefined,
    };
    
    let finalApiPayload: ContextDefinitionCreate | ContextDefinitionUpdate;
    

    if (isEditMode) {
        finalApiPayload = { 
            ...baseSubmitPayload,
            main_type: formData.main_type ? formData.main_type : undefined,
            document_source_ids: formData.main_type === ContextMainType.DOCUMENTAL ? (formData.document_source_ids || []) : undefined, 
            db_connection_config_id: formData.main_type === ContextMainType.DATABASE_QUERY ? parseInt(formData.db_connection_config_id) : undefined,
            processing_config_documental: procConfigDocPayload,
            processing_config_database_query: procConfigDbQueryPayloadForApi,
        };
    } else {
        if (!formData.main_type) { toast.error("'Tipo Principal' es obligatorio."); return; }
        finalApiPayload = { 
            ...baseSubmitPayload, 
            main_type: formData.main_type as ContextMainType,
            document_source_ids: formData.main_type === ContextMainType.DOCUMENTAL ? (formData.document_source_ids || []) : [],
            db_connection_config_id: formData.main_type === ContextMainType.DATABASE_QUERY ? parseInt(formData.db_connection_config_id) : undefined,
            processing_config_documental: procConfigDocPayload,
            processing_config_database_query: procConfigDbQueryPayloadForApi,
        };
    }
     // --- INICIO DEL PARCHE DE PRUEBA PARA TRANSFORMACIONES ---
      if (procConfigDbQueryPayloadForApi && procConfigDbQueryPayloadForApi.tools) {
        for (const tool of procConfigDbQueryPayloadForApi.tools) {
          if (tool.tool_name === "fn_app_obtener_notas_curso") {
            for (const param of tool.parameters ?? []) {
              if (param.name === "p_speriodo") {
                console.log("!!! DEBUG: Inyectando transformación REMOVE_DASHES al parámetro p_speriodo !!!");
                // `param` aquí es el objeto dentro del payload, lo modificamos directamente.
                (param as any).transformations = [ParamTransformType.REMOVE_DASHES];
              }
            }
          }
        }
      }
      // --- FIN DEL PARCHE DE PRUEBA ---
    
    // VALIDACIÓN FINAL ANTES DE ENVIAR
    if (finalApiPayload.main_type === ContextMainType.DATABASE_QUERY && !finalApiPayload.db_connection_config_id) {
        toast.error("Para un contexto de tipo 'Consulta a BD' debe seleccionar una conexión de base de datos.");
        // También puedes poner el foco en el campo si quieres: rhfMethods.setFocus('db_connection_config_id')
        return;
    }
    
    console.log("FORM_SUBMIT: Payload final para API:", deepCopy(finalApiPayload));
    await onSubmit(finalApiPayload, isEditMode);
  };
  // Clases CSS
   // --- Clases CSS (igual que antes) ---
  const labelClass = "block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1";
  const inputBaseClass = "block w-full mt-1 rounded-md shadow-sm dark:bg-slate-700 dark:text-white dark:border-slate-600 focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm disabled:opacity-60 placeholder-gray-400 dark:placeholder-gray-500";
  const inputErrorClass = "border-red-500 dark:border-red-400 focus:border-red-500 focus:ring-red-500";
  const checkboxClass = "focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300 rounded dark:bg-slate-700 dark:border-gray-500 dark:checked:bg-indigo-500 checked:bg-indigo-500";
  const fieldGroupClass = "p-4 space-y-4 bg-white dark:bg-slate-800 shadow-md sm:rounded-lg";
  const subFieldGroupClass = "p-3 space-y-3 border border-gray-300 dark:border-slate-600 rounded-md bg-slate-50 dark:bg-slate-700/60";
  const titleClass = "text-xl font-semibold text-gray-900 dark:text-white border-b border-gray-300 dark:border-slate-700 pb-3 mb-4";
  const subTitleClass = "text-md font-semibold text-gray-700 dark:text-gray-200";
  const toggleButtonClass = "text-sm text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 font-medium flex items-center py-2";
  const formHelperTextClass = "mt-1 text-xs text-gray-500 dark:text-gray-400";
  const gridLayout = "grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4";

    return (
    <form onSubmit={handleSubmit(processFormSubmit)} className="space-y-6">
      <Toaster position="top-center" />
      
      {/* SECCIÓN 1: INFORMACIÓN GENERAL */}
      <section className={fieldGroupClass}>
        <h2 className={titleClass} >Información General</h2>
        <div className={gridLayout}>
          <div>
            <label htmlFor="name" className={labelClass}>Nombre del Contexto <span className="text-red-500">*</span></label>
            <input id="name" type="text" {...register('name', { required: 'El nombre es obligatorio' })} className={`${inputBaseClass} ${errors.name ? 'border-red-500' : ''}`} />
          </div>
          <div>
            <label htmlFor="main_type" className={labelClass}>Tipo Principal <span className="text-red-500">*</span></label>
            <Controller name="main_type" control={control} rules={{ required: 'Seleccione un tipo' }}
                render={({ field }) => (
                    <select {...field} id="main_type" className={inputBaseClass}>
                        <option value="" disabled>-- Selecciona --</option>
                        {mainTypeOptions.map(opt => (<option key={opt.value} value={opt.value}>{opt.label}</option>))}
                    </select>
                )} />
          </div>
          <div className="md:col-span-2">
            <label htmlFor="description" className={labelClass}>Descripción</label>
            <textarea id="description" {...register('description')} rows={2} className={inputBaseClass} />
          </div>
          <div>
            <label htmlFor="default_llm_model_config_id" className={labelClass}>LLM por Defecto (Opcional)</label>
             <Controller name="default_llm_model_config_id" control={control} render={({ field }) => (
                <select {...field} id="default_llm_model_config_id" className={inputBaseClass} disabled={!currentMainType}>
                    <option value="">-- Usar del Perfil/Global --</option>
                    {availableLLMs.map(llm => (<option key={llm.value} value={String(llm.value)}>{llm.label}</option>))}
                </select>
            )} />
          </div>
          <div>
            <label htmlFor="virtual_agent_profile_id" className={labelClass}>Perfil de Agente (Opcional)</label>
            <Controller name="virtual_agent_profile_id" control={control} render={({ field }) => (
                <select {...field} id="virtual_agent_profile_id" className={inputBaseClass} disabled={!currentMainType}>
                    <option value="">-- Usar directo del LLM --</option>
                    {availableVAPs.map(vap => (<option key={vap.value} value={String(vap.value)}>{vap.label}</option>))}
                </select>
            )} />
          </div>
          <div className="md:col-span-2 flex items-center pt-2 space-x-8">
            <div className="flex items-center">
              <input id="is_active" type="checkbox" {...register('is_active')} className={checkboxClass}  /> 
              <label htmlFor="is_active" className="ml-2 text-sm font-medium text-gray-700 dark:text-gray-300 cursor-pointer select-none">Activo</label> 
            </div>
            <div className="flex items-center">
              <input id="is_public" type="checkbox" {...register('is_public')} className={checkboxClass}  /> 
              <label htmlFor="is_public"className="ml-2 text-sm font-medium text-gray-700 dark:text-gray-300 cursor-pointer select-none">Público</label> 
            </div>
          </div>
        </div>
      </section>

      {/* SECCIÓN 2: CONFIGURACIÓN ESPECÍFICA */}
      {currentMainType && (
          <section className={fieldGroupClass}>
            <div className="flex items-center">
                {React.createElement(mainTypeOptions.find(o=>o.value === currentMainType)?.icon || InformationCircleIcon, { className: "h-6 w-6 mr-2 text-indigo-500"})} 
                <h2 className={titleClass}>Configuración: {mainTypeOptions.find(o=>o.value === currentMainType)?.label}</h2>
            </div>

            {/* Configuración para tipo Documental */}
            {currentMainType === ContextMainType.DOCUMENTAL && (
              <div className="space-y-4 pt-2">
                    <div> {/* Document Sources */}
                        <label className={labelClass}>Fuentes de Documentos <span className="text-red-500">*</span></label>
                        <Controller name="document_source_ids" control={control} rules={{ validate: value => (currentMainType === ContextMainType.DOCUMENTAL && (!value || value.length === 0)) ? "Se requiere al menos una fuente documental." : true }}
                            render={({ field }) => (
                            isLoadingDocSources ? <p className="text-sm italic text-gray-500 dark:text-gray-400 animate-pulse">Cargando fuentes...</p> : availableDocSources.length > 0 ?
                                <div className="mt-1 space-y-1 p-3 border border-gray-300 dark:border-gray-600 rounded-md max-h-40 overflow-y-auto bg-white dark:bg-slate-700/30">
                      {availableDocSources.map(source => (
                        <div key={source.value} className="flex items-center">
                          <input id={`doc-src-${source.value}`} type="checkbox" value={source.value} checked={field.value?.includes(source.value)}
                            onChange={e => field.onChange(e.target.checked ? [...(field.value || []), Number(e.target.value)] : (field.value || []).filter(id => id !== Number(e.target.value)))}
                                        className={checkboxClass} />
                                    <label htmlFor={`doc-src-${source.value}`} className="ml-2 text-sm text-gray-700 dark:text-gray-200 cursor-pointer">{source.label}</label>
                        </div>
                      ))}
                                </div> : <p className="text-sm text-gray-500 dark:text-gray-400">No hay fuentes configuradas. <Link to="/admin/doc-sources" className="text-indigo-500 hover:underline">Crear una</Link>.</p>
                            )} />
                        {errors.document_source_ids && <p className="mt-1 text-xs text-red-500">{errors.document_source_ids.message}</p>}
                    </div>
                      
                    <div className={gridLayout}> {/* Chunk Size & Overlap */}
                        <div>
                          <label htmlFor="processing_config_documental.chunk_size" className={labelClass}>Tamaño de Chunk (Tokens) <span className="text-red-500">*</span></label>
                          <input id="processing_config_documental.chunk_size" type="number" {...register('processing_config_documental.chunk_size', {valueAsNumber: true, required: "Requerido", min: {value: 50, message:"Mín 50"}, max: {value: 4000, message:"Max 4000"} })} className={`${inputBaseClass} ${errors.processing_config_documental?.chunk_size ? inputErrorClass : ''}`} />
                          {errors.processing_config_documental?.chunk_size && <p className="mt-1 text-xs text-red-500">{errors.processing_config_documental.chunk_size.message}</p>}
                        </div>
                        <div>
                          <label htmlFor="processing_config_documental.chunk_overlap" className={labelClass}>Solapamiento Chunks (tokens) <span className="text-red-500">*</span></label>
<input 
        id="pdoc_chunk_overlap" 
        type="number" 
        {...register('processing_config_documental.chunk_overlap', {
            valueAsNumber: true, 
            required: "Requerido", 
            min: {value:0, message:"Mínimo 0"}, 
            validate: (overlapValue) => { // 'overlapValue' es el valor de este campo
                const chunkSizeValue = getValues ('processing_config_documental.chunk_size');
                
                if (typeof chunkSizeValue !== 'number' || isNaN(chunkSizeValue)) {

                    return true; 
                }
                if (typeof overlapValue !== 'number' || isNaN(overlapValue)) {
                    // Si overlapValue no es un número, otras validaciones (como 'required' o 'min') deberían manejarlo.
                    return true; // O un mensaje de error si es el caso
                }
                
                return overlapValue < chunkSizeValue || "Debe ser menor que Tamaño de Chunk";
            }
        })}
         className={`${inputBaseClass} ${errors.processing_config_documental?.chunk_overlap ? inputErrorClass : ''}`}  
        
    />                          {errors.processing_config_documental?.chunk_overlap && <p className="mt-1 text-xs text-red-500">{errors.processing_config_documental.chunk_overlap.message}</p>}
                        </div>
                </div>
              </div>
            )}
              
            {/* Configuración para tipo Consulta a BD */}
            {currentMainType === ContextMainType.DATABASE_QUERY && (
              <div className="space-y-6 pt-2">
                <div>
                  <label htmlFor="db_connection_config_id" className={labelClass}>Conexión de Base de Datos <span className="text-red-500">*</span></label>
                  <Controller name="db_connection_config_id" control={control} rules={{required: 'Seleccione una conexión'}} render={({ field }) => (
                      <select {...field} id="db_connection_config_id" className={`${inputBaseClass} ${errors.db_connection_config_id ? 'border-red-500' : ''}`}>
                          <option value="">-- Selecciona --</option>
                          {availableDbConnections.map(conn => (<option key={conn.value} value={String(conn.value)}>{conn.label}</option>))}
                      </select>
                  )} />
                </div>

                {/* --- SECCIÓN HERRAMIENTAS (STORED PROCEDURES) --- */}
                <div className={subFieldGroupClass}>
                    <h3 className={subTitleClass}>Herramientas (Stored Procedures)</h3>
                    <p className={formHelperTextClass}>Define SPs o Funciones seguras para consultas complejas. El chatbot priorizará el uso de estas herramientas.</p>
                    {toolFields.map((item, toolIndex) => (
                        <div key={item.id} className="p-4 my-2 space-y-4 relative bg-white dark:bg-slate-800 rounded-md border">
                            <IconButton type="button"  aria-label="Eliminar Herramienta" icon={<TrashIcon className="h-4 w-4"/>} onClick={() => removeTool(toolIndex)} variant="ghost" className="absolute top-2 right-2 !p-1 text-red-500" />
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div><label htmlFor={`tool_name_${toolIndex}`} className={labelClass}>Nombre de Herramienta</label><input id={`tool_name_${toolIndex}`} {...register(`processing_config_database_query.tools.${toolIndex}.tool_name`)} placeholder="ej: obtener_notas_alumno" className={inputBaseClass} /></div>
                                <div><label htmlFor={`proc_name_${toolIndex}`} className={labelClass}>Nombre Real del SP/Función</label><input id={`proc_name_${toolIndex}`} {...register(`processing_config_database_query.tools.${toolIndex}.procedure_name`)} placeholder="ej: acad.usp_get_grades" className={inputBaseClass} /></div>
                            </div>
                            <div><label htmlFor={`tool_desc_${toolIndex}`} className={labelClass}>Descripción para el LLM</label><textarea id={`tool_desc_${toolIndex}`} {...register(`processing_config_database_query.tools.${toolIndex}.description_for_llm`)} rows={2} placeholder="Cuándo y para qué usar esta herramienta (ej: 'Útil para obtener las notas de un alumno')" className={inputBaseClass} /></div>
                            <ToolParametersControl toolIndex={toolIndex} control={control} register={register} />
                        </div>
                    ))}
                    {toolFields.length === 0 && <p className="text-sm text-gray-500 dark:text-gray-400">No hay herramientas definidas. Añade una para mejorar las consultas.</p>}
                    <Button type="button" onClick={addToolItem} isLoading={isLoadingDbTables} disabled={!watchedDbConnectionId} icon={<PlusCircleIcon className="h-5 w-5"/>}>
                            {isLoadingDbTables ? 'Cargando...' : 'Añadir Herramienta'}
                    </Button>


                </div>

                {/* --- SECCIÓN MODO GENERALISTA (ACCESO POR TABLAS) --- */}
                <div className={subFieldGroupClass}>
                    <h3 className={subTitleClass}>Modo Generalista (Acceso por Tablas)</h3>
                    <p className={formHelperTextClass}>Permite al chatbot generar SQL sobre tablas específicas. Usar como alternativa cuando ninguna herramienta aplique.</p>
                    <div className="flex items-end gap-x-4">
                        <div className="flex-grow">
                            <label className={labelClass}>Tablas Permitidas</label>
                            <CreatableMultiSelect name="processing_config_database_query.selected_schema_tables_for_llm" control={control} placeholder={dbSchemaTableOptions.length > 0 ? "Selecciona de la lista..." : "Inspecciona la BD para poblar"} isDisabled={!watchedDbConnectionId} options={dbSchemaTableOptions} />
                        </div>
                        <Button type="button" onClick={handleInspectClick} isLoading={isLoadingDbTables} disabled={!watchedDbConnectionId} icon={<ArrowPathIcon className="h-5 w-5"/>}>
                            {isLoadingDbTables ? 'Cargando...' : 'Inspeccionar'}
                        </Button>
                    </div>
                    {isErrorDbTables && <p className="mt-1 text-xs text-red-500">Error al inspeccionar la BD. Revisa permisos y la consola.</p>}
                    
                    <div className="pt-3">
                      <button type="button" onClick={() => setIsSqlPolicyExpanded(prev => !prev)} className="text-sm text-indigo-600 font-medium flex items-center">
                        {isSqlPolicyExpanded ? <ChevronUpIcon className="h-5 w-5 mr-1"/> : <ChevronDownIcon className="h-5 w-5 mr-1"/>}
                        Política de Selección SQL (Avanzado)
                      </button>
                      {isSqlPolicyExpanded && (
                        <div className={`${subFieldGroupClass} mt-2`}>
                          <h3 className={subTitleClass + " pb-2 border-b dark:border-slate-500"}>Parámetros Generales de SQL</h3>
                          <div className={gridLayout}>
                            <div>
                              <label htmlFor="sql_default_select_limit" className={labelClass}>Límite Filas Default <span className="text-red-500">*</span></label>
                              <input id="sql_default_select_limit" type="number" {...register('processing_config_database_query.sql_select_policy.default_select_limit', {valueAsNumber:true, required:true, min:0})} className={`${inputBaseClass} ${errors.processing_config_database_query?.sql_select_policy?.default_select_limit ? inputErrorClass : ''}`}/>
                              {errors.processing_config_database_query?.sql_select_policy?.default_select_limit && <p className="mt-1 text-xs text-red-500">{errors.processing_config_database_query.sql_select_policy.default_select_limit.message}</p>}
                            </div>
                             <div>
                              <label htmlFor="sql_max_select_limit" className={labelClass}>Límite Filas Máximo <span className="text-red-500">*</span></label>
                              <input id="sql_max_select_limit" type="number" {...register('processing_config_database_query.sql_select_policy.max_select_limit', {valueAsNumber:true, required:true, min:0})} className={`${inputBaseClass} ${errors.processing_config_database_query?.sql_select_policy?.max_select_limit ? inputErrorClass : ''}`}/>
                              {errors.processing_config_database_query?.sql_select_policy?.max_select_limit && <p className="mt-1 text-xs text-red-500">{errors.processing_config_database_query.sql_select_policy.max_select_limit.message}</p>}
                            </div>
                          </div>
                          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 pt-2">
                              {/* Checkboxes para allow_... */}
                              {(['allow_joins', 'allow_aggregations', 'allow_group_by', 'allow_order_by', 'allow_where_clauses'] as const).map(key => (
                                  <div key={key} className="flex items-center">
                                      <input id={`sql_${key}`} type="checkbox" {...register(`processing_config_database_query.sql_select_policy.${key}`)} className={checkboxClass} />
                                      <label htmlFor={`sql_${key}`} className="ml-2 text-sm text-gray-700 dark:text-gray-200">
                                          {key.replace('allow_', 'Permitir ').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                                      </label>
                                  </div>
                              ))}
                          </div>
                          <div>
                               <label htmlFor="sql_allowed_join_types" className={labelClass}>Tipos de Join Permitidos</label>
                                <CreatableMultiSelect
                                    id="sql_allowed_join_types"
                                    name="processing_config_database_query.sql_select_policy.allowed_join_types" // Nombre completo del campo
                                    control={control} // El control del useForm principal
                                    placeholder="Añadir tipo (ej. INNER) y Enter"
                                    options={['INNER', 'LEFT', 'RIGHT', 'FULL OUTER'].map(s => ({label:s, value:s}))}
                                    // noOptionsMessage, formatCreateLabel, etc. si los necesitas
                                />
                          </div>
                           
                           <div>
                              <label htmlFor="sql_allowed_aggregation_functions" className={labelClass}>Funciones de Agregación Permitidas</label>
                              <CreatableMultiSelect // USO DIRECTO
                                  id="sql_allowed_aggregation_functions"
                                  name="processing_config_database_query.sql_select_policy.allowed_aggregation_functions"
                                  control={control}
                                  placeholder="Añadir función (ej. COUNT) y Enter" 
                                  options={['COUNT', 'SUM', 'AVG', 'MIN', 'MAX'].map(s => ({label:s, value:s}))}
                              />
                          </div>
                           <div>
                              <label htmlFor="sql_forbidden_keywords" className={labelClass}>Palabras Clave Prohibidas en WHERE</label>
                              <CreatableMultiSelect // USO DIRECTO
                                  id="sql_forbidden_keywords"
                                  name="processing_config_database_query.sql_select_policy.forbidden_keywords_in_where"
                                  control={control}
                                  placeholder="Añadir palabra (ej. DELETE) y Enter"
                                  // options (puede no tener predefinidos o tener algunos comunes)
                              />
                          </div>

                          {/* Column Access Rules */}
                          <div className="pt-3">
                            <h4 className={subTitleClass + " pb-1 mb-2 border-b dark:border-slate-500"}>Reglas de Acceso por Tabla/Columna</h4>
                            {columnAccessRulesFields.map((item, index) => (
                                <div key={item.id} className={`${subFieldGroupClass} bg-slate-100 dark:bg-slate-700/70 p-3 my-2 space-y-3 relative`}>
                                    <IconButton type="button" aria-label="Eliminar Regla" icon={<TrashIcon className="h-4 w-4"/>} onClick={() => removeRule(index)} variant="ghost" className="absolute top-1 right-1 !p-1 text-red-500 hover:bg-red-100 dark:hover:bg-red-700/50" />
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                        <div className="md:col-span-3">
                                          <label htmlFor={`car_table_name_${index}`} className={labelClass}>Nombre Tabla (schema.tabla) <span className="text-red-500">*</span></label>
                                          <input id={`car_table_name_${index}`} {...register(`processing_config_database_query.sql_select_policy.column_access_rules.${index}.table_name` as const, {required: "Nombre de tabla es requerido"})} placeholder="ej. public.ventas" className={`${inputBaseClass} ${errors.processing_config_database_query?.sql_select_policy?.column_access_rules?.[index]?.table_name ? inputErrorClass : ''}`} />
                                          {errors.processing_config_database_query?.sql_select_policy?.column_access_rules?.[index]?.table_name && <p className="text-xs text-red-500 mt-1">{errors.processing_config_database_query?.sql_select_policy?.column_access_rules?.[index]?.table_name?.message}</p>}
                                        </div>
                                        <div className="md:col-span-3">
                                          <CreatableMultiSelect 
                                            label="Columnas Permitidas (Opcional)" 
                                            id={`car_allowed_${index}`}
                                            name={`processing_config_database_query.sql_select_policy.column_access_rules.${index}.column_policy.allowed_columns` as const}
                                            control={control}
                                            placeholder="Añadir columna y Enter..." /> 
                                        </div>
                                        <div className="md:col-span-3">
                                           <CreatableMultiSelect 
                                            label="Columnas Prohibidas (Opcional)" 
                                            id={`car_forbidden_${index}`}
                                            name={`processing_config_database_query.sql_select_policy.column_access_rules.${index}.column_policy.forbidden_columns` as const}
                                            control={control}
                                            placeholder="Añadir columna y Enter..."/>
                                        </div>
                                    </div>
                                </div>
                            ))}
                            
                            <Button type="button" onClick={addColumnAccessRuleItem} isLoading={isLoadingDbTables} disabled={!watchedDbConnectionId} icon={<PlusCircleIcon className="h-5 w-5"/>}>
                            {isLoadingDbTables ? 'Cargando...' : 'Añadir Regla de Tabla'}
                          </Button>
                          </div>
                        </div>
                      )}
                    </div>
                </div>
              </div>
            )}
        </section>
      )}

      <div className="mt-8 pt-6 border-t dark:border-gray-700 flex flex-col sm:flex-row justify-end items-center space-y-3 sm:space-y-0 sm:space-x-3">
        <Link to="/admin/context-definitions" className="text-sm text-gray-600 dark:text-gray-400 hover:underline text-center sm:text-left">
            Volver a la lista
        </Link>
        <Button type="button" variant="secondary" onClick={onCancel} disabled={isSubmittingGlobal}>Cancelar</Button>
        <Button type="submit" 
            disabled={isSubmittingGlobal || !isFormValid || (!isDirty && isEditMode) } 
            isLoading={isSubmittingGlobal} 
            className="w-full sm:w-auto"
        >
            {isSubmittingGlobal ? 'Guardando...' : (isEditMode ? 'Guardar Cambios' : 'Crear Contexto')}
        </Button>
        
      </div>
    </form>
  );
};

export default ContextDefinitionForm;
