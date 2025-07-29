// src/components/admin/context-definitions/ContextDefinitionForm.tsx
import React, { useEffect, useState } from 'react'; // useCallback no se usa, lo quité
import { useForm, Controller, type SubmitHandler, useFieldArray } from 'react-hook-form';
import toast, { Toaster } from 'react-hot-toast';

// Tipos generados por Orval
import {
  type ContextDefinitionCreate,
  type ContextDefinitionUpdate,
  type ContextDefinitionResponse,
  ContextMainType,
  type DocumentSourceResponse, // Para mostrar en el dropdown/selector de sources
  // Tipos para los processing_config y sus sub-schemas
  type DocumentalProcessingConfigSchema,
  type DatabaseQueryProcessingConfigSchema as ApiDatabaseQueryProcessingConfigSchemaOutput, // Este es el que viene en GET
  type SqlSelectPolicySchema as ApiSqlSelectPolicyOutput,         // Anidado en el de arriba para GET
  type SqlTableAccessRuleSchema as ApiSqlTableAccessRuleSchema,     // Anidado
  type SqlColumnAccessPolicySchema as ApiSqlColumnAccessPolicySchema, // Anidado
  // Para los payloads de POST/PUT, si Orval generó tipos Input específicos (ej. desde requestBody en OpenAPI)
  // Deberíamos usarlos. Basado en tu sqlSelectPolicySchemaInput.ts:
  type SqlSelectPolicySchemaInput as ApiSqlSelectPolicyInput,
  // Si existe un DatabaseQueryProcessingConfigSchemaInput, sería bueno usarlo
  // por ahora asumimos que la estructura de ApiDatabaseQueryProcessingConfigSchemaOutput
  // es compatible o es la que se espera en el body del POST/PUT para processing_config_database_query
} from '../../../services/api/schemas'; 

// Hooks de React Query (TanStack Query)
import {
  useReadAllDocumentSourcesApiV1AdminDocSourcesGet,
  useReadAllDbConnectionsApiV1AdminDbConnectionsGet,
  useReadAllLlmModelConfigsApiV1AdminLlmModelsGet as useReadAllLlmModelConfigsApiV1AdminLlmModelsLlmModelsGet ,
  useReadAllVirtualAgentProfilesApiV1AdminVirtualAgentProfilesGet,
} from '../../../services/api/endpoints';

// Otros componentes y utilidades
import { Link } from 'react-router-dom';
import CreatableMultiSelect from '../../shared/forms/CreatableMultiSelect';
import { Button, IconButton } from '../../shared/Button';
import { PlusCircleIcon, TrashIcon, InformationCircleIcon, ChevronDownIcon, ChevronUpIcon, DocumentTextIcon, CommandLineIcon, BeakerIcon } from '@heroicons/react/24/outline';

// Helper deepCopy (idealmente en un archivo utils.ts e importado)
const deepCopy = <T,>(obj: T): T => {
    if (obj === null || typeof obj !== 'object') { return obj; }
    if (obj instanceof Date) { return new Date(obj.getTime()) as any; }
    if (Array.isArray(obj)) { return obj.map(item => deepCopy(item)) as any; }
    const copiedObject = {} as { [P in keyof T]: T[P] };
    for (const key in obj) {
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        copiedObject[key] = deepCopy(obj[key]);
      }
    }
    return copiedObject;
};

// Props del formulario
interface ContextDefinitionFormProps {
  initialData?: ContextDefinitionResponse | null;
  onSubmit: (data: ContextDefinitionCreate | ContextDefinitionUpdate, isEditMode: boolean) => Promise<void>;
  onCancel: () => void;
  isSubmittingGlobal: boolean;
  isEditMode: boolean;
}

// --- Tipos Internos para el Formulario React Hook Form ---
type FormSqlColumnPolicy = {
  allowed_columns: string[];
  forbidden_columns: string[];
};

type FormSqlTableRule = {
  id?: string; // Para useFieldArray key
  table_name: string; 
  column_policy: FormSqlColumnPolicy; 
};

// El sql_select_policy dentro del formulario (para edición).
// No tiene 'allowed_tables_for_select' porque eso se maneja con el campo 'selected_schema_tables_for_llm' a un nivel superior.
// Se basa en ApiSqlSelectPolicyOutput para los campos que sí queremos que el usuario edite aquí.
type FormSqlSelectPolicy = Omit<ApiSqlSelectPolicyOutput, 'column_access_rules' | 'column_access_policy_from_db' | 'allowed_tables_for_select'> & {
  column_access_rules: FormSqlTableRule[];
};

// Tipo para la parte `processing_config_database_query` de los FormValues.
type FormProcessingConfigDBQuery = Omit<ApiDatabaseQueryProcessingConfigSchemaOutput, 'custom_table_descriptions' | 'sql_select_policy' | 'selected_schema_tables_for_llm'> & {
  selected_schema_tables_for_llm: string[]; // Este es el campo del formulario donde el usuario selecciona las tablas.
  custom_table_descriptions_json: string;  // Para editar el JSON de descripciones.
  sql_select_policy: FormSqlSelectPolicy;    // El tipo de policy anidado que definimos arriba.
};

// El tipo completo para los valores del formulario.
type FormValues = {
  name: string;
  description: string | null;
  is_active: boolean;
  is_public: boolean; // <--- 1. AÑADE ESTA LÍNEA
  main_type: ContextMainType | '';
  default_llm_model_config_id: string;
  virtual_agent_profile_id: string;
  document_source_ids: number[];
  db_connection_config_id: string;
  processing_config_documental: DocumentalProcessingConfigSchema; // Usa el tipo API directamente
  processing_config_database_query: FormProcessingConfigDBQuery;   // Usa nuestro tipo de Form
};

// --- Valores por Defecto para Inicialización del Formulario ---
const defaultDocConfigValues: DocumentalProcessingConfigSchema = { 
  chunk_size: 1000, 
  chunk_overlap: 200, 
  rag_prompts: undefined // Si DocumentalProcessingConfigSchema lo permite opcional
};
const defaultSqlColumnPolicyValues: FormSqlColumnPolicy = { allowed_columns: [], forbidden_columns: [] };
const defaultSqlTableRuleValues: FormSqlTableRule = { table_name: '', column_policy: deepCopy(defaultSqlColumnPolicyValues) };

const defaultFormSqlSelectPolicy: FormSqlSelectPolicy = {
    default_select_limit: 10, max_select_limit: 50, allow_joins: true,
    allowed_join_types: ["INNER", "LEFT"], allow_aggregations: true,
    allowed_aggregation_functions: ["COUNT", "SUM", "AVG", "MIN", "MAX"],
    allow_group_by: true, allow_order_by: true, allow_where_clauses: true,
    forbidden_keywords_in_where: ["DELETE", "UPDATE", "INSERT", "DROP", "TRUNCATE", "EXEC", "ALTER", "CREATE", "GRANT", "REVOKE"],
    column_access_rules: [], llm_instructions_for_select: [],
};

const defaultDbQueryConfigValues: FormProcessingConfigDBQuery = {
  schema_info_type: "dictionary_table_sqlserver_custom", 
  dictionary_table_query: undefined, // O null
  selected_schema_tables_for_llm: [], // El campo del form
  custom_table_descriptions_json: '{}',
  db_schema_chunk_size: 2000, 
  db_schema_chunk_overlap: 200,
  sql_select_policy: deepCopy(defaultFormSqlSelectPolicy)
};

const defaultFormValues: FormValues = {
    name: '', description: null, is_active: true, main_type: '',
    is_public: true, // <--- 2. AÑADE ESTA LÍNEA (por defecto es público)
    default_llm_model_config_id: '', virtual_agent_profile_id: '',
    document_source_ids: [], db_connection_config_id: '',
    processing_config_documental: deepCopy(defaultDocConfigValues),
    processing_config_database_query: deepCopy(defaultDbQueryConfigValues),
};

const mainTypeOptions: Array<{ value: ContextMainType; label: string; icon: React.ElementType }> = [
  { value: ContextMainType.DOCUMENTAL, label: 'Contenido Documental', icon: DocumentTextIcon },
  { value: ContextMainType.DATABASE_QUERY, label: 'Consulta a BD (Text-to-SQL)', icon: CommandLineIcon },
  // { value: ContextMainType.IMAGE_ANALYSIS, label: 'Análisis de Imágenes', icon: PhotoIcon } // Si lo añades
];

// --- Componente del Formulario ---
const ContextDefinitionForm: React.FC<ContextDefinitionFormProps> = ({
  initialData, onSubmit, onCancel, isSubmittingGlobal, isEditMode,
}) => {
  const rhfMethods = useForm<FormValues>({ mode: 'onChange', defaultValues: deepCopy(defaultFormValues) });
  const { register, handleSubmit, reset, control, watch, setValue, getValues, trigger, formState: { errors, isDirty, isValid: isFormValid }, } = rhfMethods;

  const currentMainType = watch('main_type');
  const watchedDbConnectionId = watch('db_connection_config_id');
  const watchedDocProcessingChunkSize = watch('processing_config_documental.chunk_size');
  
  const [dbSchemaTableOptions, setDbSchemaTableOptions] = useState<Array<{ label: string, value: string }>>([]);
  const [isLoadingDbTables, setIsLoadingDbTables] = useState(false);
  const [isSqlPolicyExpanded, setIsSqlPolicyExpanded] = useState(false);
  const [testQueryFeedback, setTestQueryFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const commonQueryOptions = { query: { staleTime: 5 * 60 * 1000 } };
  const { data: docSourcesData, isLoading: isLoadingDocSources } = useReadAllDocumentSourcesApiV1AdminDocSourcesGet({ limit: 1000 }, { ...commonQueryOptions, query: { ...commonQueryOptions.query, enabled: currentMainType === ContextMainType.DOCUMENTAL } });
  const availableDocSources = (docSourcesData || []).map(ds => ({ value: ds.id, label: `${ds.name} (${ds.source_type})`}));

  const { data: dbConnectionsData, isLoading: isLoadingDbConnections } = useReadAllDbConnectionsApiV1AdminDbConnectionsGet({ limit: 500 }, { ...commonQueryOptions, query: { ...commonQueryOptions.query, enabled: currentMainType === ContextMainType.DATABASE_QUERY } });
  const availableDbConnections = (dbConnectionsData || []).map(conn => ({ value: conn.id, label: `${conn.name} (${conn.db_type})`}));
  
  const { data: llmModelsData, isLoading: isLoadingLLMs } = useReadAllLlmModelConfigsApiV1AdminLlmModelsLlmModelsGet({ limit: 500 }, { ...commonQueryOptions, query: { ...commonQueryOptions.query, enabled: !!currentMainType }});
  const availableLLMs = (llmModelsData || []).map(llm => ({ value: llm.id, label: `${llm.display_name} (${llm.provider})` }));

  const { data: vapsData, isLoading: isLoadingVAPs } = useReadAllVirtualAgentProfilesApiV1AdminVirtualAgentProfilesGet({ limit: 500 }, { ...commonQueryOptions, query: { ...commonQueryOptions.query, enabled: !!currentMainType }});
  const availableVAPs = (vapsData || []).map(vap => ({ value: vap.id, label: vap.name }));

  useEffect(() => {
    if (getValues('processing_config_documental.chunk_size') !== undefined && getValues('processing_config_documental.chunk_overlap') !== undefined) {
      trigger('processing_config_documental.chunk_overlap');
    }
  }, [watchedDocProcessingChunkSize, trigger, getValues]);

  useEffect(() => { // Carga simulada de tablas de BD
    const connIdNum = parseInt(watchedDbConnectionId, 10);
    if (currentMainType === ContextMainType.DATABASE_QUERY && connIdNum && !isNaN(connIdNum)) {
      setIsLoadingDbTables(true); console.log("FORM_EFFECT[DB_TABLES]: Cargando (simulado) para connId:", connIdNum);
      // TODO: Implementar endpoint backend `/api/v1/admin/db-connections/{connId}/list-tables`
      // TODO: Crear hook TanStack Query `useListTablesForDbConnection(connId)`
      setTimeout(() => {
        const simulated = [`dbo.FactVentas_conn${connIdNum}`, `dbo.DimCliente_conn${connIdNum}`, `production.Product_conn${connIdNum}`];
        setDbSchemaTableOptions(simulated.map(name => ({ label: name, value: name })));
        setIsLoadingDbTables(false); console.log("FORM_EFFECT[DB_TABLES]: Simulación completa.", simulated);
      }, 1500);
    } else {
      setDbSchemaTableOptions([]);
      if (getValues('processing_config_database_query.selected_schema_tables_for_llm')?.length > 0) {
        setValue('processing_config_database_query.selected_schema_tables_for_llm', []);
      }
    }
  }, [currentMainType, watchedDbConnectionId, setValue, getValues]);

  useEffect(() => { // Reset del formulario al editar o crear
    console.log("FORM_EFFECT[RESET]: Triggered. isEditMode:", isEditMode, "initialData:", initialData ? {id:initialData.id, name: initialData.name, main_type: initialData.main_type} : null);
    if (isEditMode && initialData) {
      const apiPConfigDoc = initialData.processing_config_documental; // Tipo: DocumentalProcessingConfigSchema | null | undefined
      const apiPConfigDb = initialData.processing_config_database_query; // Tipo: ApiDatabaseQueryProcessingConfigSchemaOutput | null | undefined
      
      console.log("FORM_EFFECT[RESET]: initialData.processing_config_database_query (API Output):", JSON.stringify(apiPConfigDb, null, 2));

      const formColumnAccessRules: FormSqlTableRule[] = 
        apiPConfigDb?.sql_select_policy?.column_access_rules?.map((apiRule: ApiSqlTableAccessRuleSchema, index) => ({
          id: `loaded-rule-${apiRule.table_name}-${index}`, 
          table_name: apiRule.table_name || '',
          column_policy: { 
            allowed_columns: apiRule.column_policy?.allowed_columns || [],
            forbidden_columns: apiRule.column_policy?.forbidden_columns || [],
          }
        })) || [];
      
      const valuesToSet: FormValues = {
        name: initialData.name || '',
        description: initialData.description || null,
        is_active: typeof initialData.is_active === 'boolean' ? initialData.is_active : true,
        is_public: typeof initialData.is_public === 'boolean' ? initialData.is_public : true, 
        main_type: initialData.main_type || '',
        default_llm_model_config_id: String(initialData.default_llm_model_config_id ?? initialData.default_llm_model_config?.id ?? ''),
        virtual_agent_profile_id: String(initialData.virtual_agent_profile_id ?? initialData.virtual_agent_profile?.id ?? ''),
        document_source_ids: initialData.document_sources?.map(ds => ds.id) || [],
        db_connection_config_id: String(initialData.db_connection_config?.id ?? ''), // Nota: Pydantic response lo llama db_connection_config
        
        processing_config_documental: apiPConfigDoc 
            ? { ...deepCopy(defaultDocConfigValues), ...apiPConfigDoc } 
            : deepCopy(defaultDocConfigValues),
            
        processing_config_database_query: apiPConfigDb
            ? { 
                ...deepCopy(defaultDbQueryConfigValues), 
                schema_info_type: apiPConfigDb.schema_info_type || defaultDbQueryConfigValues.schema_info_type,
                dictionary_table_query: apiPConfigDb.dictionary_table_query || defaultDbQueryConfigValues.dictionary_table_query,
                custom_table_descriptions_json: JSON.stringify(apiPConfigDb.custom_table_descriptions || {}, null, 2),
                db_schema_chunk_size: apiPConfigDb.db_schema_chunk_size ?? defaultDbQueryConfigValues.db_schema_chunk_size,
                db_schema_chunk_overlap: apiPConfigDb.db_schema_chunk_overlap ?? defaultDbQueryConfigValues.db_schema_chunk_overlap,
                // Poblar selected_schema_tables_for_llm del form con allowed_tables_for_select de la policy (API Output)
                selected_schema_tables_for_llm: apiPConfigDb.sql_select_policy?.allowed_tables_for_select || [],
                
                sql_select_policy: apiPConfigDb.sql_select_policy // apiPConfigDb.sql_select_policy es ApiSqlSelectPolicySchemaOutput
                    ? { // Mapear a FormSqlSelectPolicy (que no tiene allowed_tables_for_select directamente)
                        ...deepCopy(defaultFormSqlSelectPolicy), // Usa el default específico para la forma del form
                        // Copiar campos compatibles
                        default_select_limit: apiPConfigDb.sql_select_policy.default_select_limit ?? defaultFormSqlSelectPolicy.default_select_limit,
                        max_select_limit: apiPConfigDb.sql_select_policy.max_select_limit ?? defaultFormSqlSelectPolicy.max_select_limit,
                        allow_joins: apiPConfigDb.sql_select_policy.allow_joins ?? defaultFormSqlSelectPolicy.allow_joins,
                        allowed_join_types: apiPConfigDb.sql_select_policy.allowed_join_types || [],
                        allow_aggregations: apiPConfigDb.sql_select_policy.allow_aggregations ?? defaultFormSqlSelectPolicy.allow_aggregations,
                        allowed_aggregation_functions: apiPConfigDb.sql_select_policy.allowed_aggregation_functions || [],
                        allow_group_by: apiPConfigDb.sql_select_policy.allow_group_by ?? defaultFormSqlSelectPolicy.allow_group_by,
                        allow_order_by: apiPConfigDb.sql_select_policy.allow_order_by ?? defaultFormSqlSelectPolicy.allow_order_by,
                        allow_where_clauses: apiPConfigDb.sql_select_policy.allow_where_clauses ?? defaultFormSqlSelectPolicy.allow_where_clauses,
                        forbidden_keywords_in_where: apiPConfigDb.sql_select_policy.forbidden_keywords_in_where || [],
                        column_access_rules: formColumnAccessRules, 
                        llm_instructions_for_select: apiPConfigDb.sql_select_policy.llm_instructions_for_select || [],
                      }
                    : deepCopy(defaultFormSqlSelectPolicy),
              }
            : deepCopy(defaultDbQueryConfigValues),
      };
      console.log("FORM_EFFECT[RESET]: Valores finales para reset:", JSON.parse(JSON.stringify(valuesToSet)));
      reset(valuesToSet);
      setIsSqlPolicyExpanded(!!(apiPConfigDb?.sql_select_policy));
    } else if (!isEditMode) {
      console.log("FORM_EFFECT[RESET]: Modo Creación, usando defaultFormValues.");
      reset(deepCopy(defaultFormValues)); 
      setIsSqlPolicyExpanded(false);
    }
  }, [initialData, isEditMode, reset]); // Dependencias del efecto

  const { fields: columnAccessRulesFields, append: appendCAR, remove: removeCAR } = useFieldArray({
    control, name: "processing_config_database_query.sql_select_policy.column_access_rules", keyName: "id"
  });
  const addColumnAccessRuleItem = () => appendCAR(deepCopy(defaultSqlTableRuleValues));
  const removeColumnAccessRuleItem = (index: number) => removeCAR(index);
  
  const processFormSubmit: SubmitHandler<FormValues> = async (formData) => {
    console.log("FORM_SUBMIT: Datos crudos del formulario (FormValues):", JSON.parse(JSON.stringify(formData)));
    let procConfigDocPayload: DocumentalProcessingConfigSchema | undefined = undefined;
    // El payload para el campo `processing_config_database_query` en ContextDefinitionCreate/Update
    // debe ser del tipo `DatabaseQueryProcessingConfigSchemaInput` (o el tipo general si Orval no generó uno de Input)
    let procConfigDbQueryPayloadForApi: ApiDatabaseQueryProcessingConfigSchemaOutput | undefined = undefined; 
    // Usamos ApiDatabaseQueryProcessingConfigSchemaOutput como placeholder para la estructura,
    // ya que es el más completo que tenemos importado y la parte `sql_select_policy` interna 
    // se ajustará para que sea compatible con `ApiSqlSelectPolicyInput`.

    if (formData.main_type === ContextMainType.DOCUMENTAL) {
      procConfigDocPayload = {
        chunk_size: Number(formData.processing_config_documental.chunk_size),
        chunk_overlap: Number(formData.processing_config_documental.chunk_overlap),
        rag_prompts: formData.processing_config_documental.rag_prompts || undefined,
      };
    } else if (formData.main_type === ContextMainType.DATABASE_QUERY) {
      let customDescs: Record<string, string> = {};
      try {
        customDescs = JSON.parse(formData.processing_config_database_query.custom_table_descriptions_json.trim() || '{}');
        if (typeof customDescs !== 'object' || customDescs === null || Array.isArray(customDescs)) throw new Error("Debe ser un objeto JSON.");
      } catch(e: any) { toast.error(`JSON de Descripciones Personalizadas es inválido: ${e.message}`); return; }
      
      // Construir el objeto para sql_select_policy compatible con ApiSqlSelectPolicyInput
      const sqlPolicyForApi: ApiSqlSelectPolicyInput = {
        default_select_limit: Number(formData.processing_config_database_query.sql_select_policy.default_select_limit),
        max_select_limit: Number(formData.processing_config_database_query.sql_select_policy.max_select_limit),
        allow_joins: !!formData.processing_config_database_query.sql_select_policy.allow_joins,
        allowed_join_types: formData.processing_config_database_query.sql_select_policy.allowed_join_types || [],
        allow_aggregations: !!formData.processing_config_database_query.sql_select_policy.allow_aggregations,
        allowed_aggregation_functions: formData.processing_config_database_query.sql_select_policy.allowed_aggregation_functions || [],
        allow_group_by: !!formData.processing_config_database_query.sql_select_policy.allow_group_by,
        allow_order_by: !!formData.processing_config_database_query.sql_select_policy.allow_order_by,
        allow_where_clauses: !!formData.processing_config_database_query.sql_select_policy.allow_where_clauses,
        forbidden_keywords_in_where: formData.processing_config_database_query.sql_select_policy.forbidden_keywords_in_where || [],
        // Usar el valor de selected_schema_tables_for_llm del formulario para el payload de la API
        allowed_tables_for_select: formData.processing_config_database_query.selected_schema_tables_for_llm || [],
        // column_access_rules (lista de FormSqlTableRule) se convierte a ApiSqlTableAccessRuleSchema[]
        // y el backend las convierte a column_access_policy (dict) si es necesario al guardar en BD.
        column_access_rules: formData.processing_config_database_query.sql_select_policy.column_access_rules.map(formRule => ({
            table_name: formRule.table_name,
            column_policy: { 
                allowed_columns: formRule.column_policy.allowed_columns || [],
                forbidden_columns: formRule.column_policy.forbidden_columns || [],
            } as ApiSqlColumnAccessPolicySchema // El tipo de API para este sub-objeto
        })),
        llm_instructions_for_select: formData.processing_config_database_query.sql_select_policy.llm_instructions_for_select || [],
        // No se envía column_access_policy, ya que se genera desde column_access_rules si es necesario
      };

      procConfigDbQueryPayloadForApi = {
        schema_info_type: formData.processing_config_database_query.schema_info_type,
        dictionary_table_query: formData.processing_config_database_query.dictionary_table_query || undefined,
        selected_schema_tables_for_llm: formData.processing_config_database_query.selected_schema_tables_for_llm || [],
        custom_table_descriptions: customDescs,
        db_schema_chunk_size: Number(formData.processing_config_database_query.db_schema_chunk_size),
        db_schema_chunk_overlap: Number(formData.processing_config_database_query.db_schema_chunk_overlap),
        sql_select_policy: sqlPolicyForApi, // Aquí sqlPolicyForApi ya es del tipo correcto
      };
    }

    const baseSubmitPayload = {
      name: formData.name.trim(),
      description: formData.description?.trim() || null,
      is_active: formData.is_active,
      is_public: formData.is_public, 
      default_llm_model_config_id: formData.default_llm_model_config_id ? parseInt(formData.default_llm_model_config_id) : null,
      virtual_agent_profile_id: formData.virtual_agent_profile_id ? parseInt(formData.virtual_agent_profile_id) : null,
    };

    let finalApiPayload: ContextDefinitionCreate | ContextDefinitionUpdate;

    if (isEditMode) {
        finalApiPayload = { 
            ...baseSubmitPayload,
            main_type: formData.main_type ? formData.main_type as ContextMainType : undefined,
            document_source_ids: formData.main_type === ContextMainType.DOCUMENTAL ? (formData.document_source_ids || []) : undefined, 
            db_connection_config_id: formData.main_type === ContextMainType.DATABASE_QUERY && formData.db_connection_config_id ? parseInt(formData.db_connection_config_id) : undefined,
            processing_config_documental: formData.main_type === ContextMainType.DOCUMENTAL ? procConfigDocPayload : undefined,
            processing_config_database_query: formData.main_type === ContextMainType.DATABASE_QUERY ? procConfigDbQueryPayloadForApi : undefined,
        };
    } else {
        if (!formData.main_type) { toast.error("'Tipo Principal' es obligatorio."); return; }
        finalApiPayload = { 
            ...baseSubmitPayload, 
            main_type: formData.main_type as ContextMainType,
            document_source_ids: formData.document_source_ids || [],
            db_connection_config_id: formData.db_connection_config_id ? parseInt(formData.db_connection_config_id) : null,
            processing_config_documental: procConfigDocPayload,
            processing_config_database_query: procConfigDbQueryPayloadForApi,
        };
    }
    
    console.log("FORM_SUBMIT: Payload final para API (después de transformaciones):", JSON.parse(JSON.stringify(finalApiPayload)));
    await onSubmit(finalApiPayload, isEditMode);
  };

  
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


  function removeRule(index: any): void {
    throw new Error('Function not implemented.');
  }

  return (
    <form onSubmit={handleSubmit(processFormSubmit)} className="space-y-6">
      <Toaster position="top-center" />
      
      <section className={fieldGroupClass}>
        <h2 className={titleClass}>Información General</h2>
        <div className={gridLayout}>
          <div>
            <label htmlFor="name" className={labelClass}>Nombre del Contexto <span className="text-red-500">*</span></label>
            <input id="name" type="text" {...register('name', { required: 'El nombre es obligatorio', minLength: { value: 3, message: 'Mín. 3 caract.' }, maxLength: { value: 150, message: 'Máx. 150 caract.' }})} className={`${inputBaseClass} ${errors.name ? inputErrorClass : ''}`} />
            {errors.name && <p className="mt-1 text-xs text-red-500">{errors.name.message}</p>}
          </div>
          <div>
            <label htmlFor="main_type" className={labelClass}>Tipo Principal <span className="text-red-500">*</span></label>
            <Controller name="main_type" control={control} rules={{ required: 'Seleccione un tipo' }}
                render={({ field }) => (
                    <select {...field} id="main_type" className={`${inputBaseClass} ${errors.main_type ? inputErrorClass : ''}`}>
                        <option value="" disabled>-- Selecciona tipo --</option>
                        {mainTypeOptions.map(opt => (<option key={opt.value} value={opt.value}>{opt.label}</option>))}
                    </select>
                )} />
            {errors.main_type && <p className="mt-1 text-xs text-red-500">{errors.main_type.message}</p>}
          </div>
          <div className="md:col-span-2">
            <label htmlFor="description" className={labelClass}>Descripción</label>
            <textarea id="description" {...register('description')} rows={2} className={`${inputBaseClass}`} />
          </div>
          <div>
            <label htmlFor="default_llm_model_config_id" className={labelClass}>LLM por Defecto</label>
             <Controller name="default_llm_model_config_id" control={control}
                render={({ field }) => (
                    <select {...field} id="default_llm_model_config_id" className={`${inputBaseClass} ${errors.default_llm_model_config_id ? inputErrorClass : ''}`} disabled={isLoadingLLMs || !currentMainType}>
                        <option value="">{isLoadingLLMs ? "Cargando LLMs..." : (currentMainType ? "Ninguno (Usar del Perfil/Global)" : "Selecciona Tipo Principal")}</option>
                        {availableLLMs.map(llm => (<option key={llm.value} value={String(llm.value)}>{llm.label}</option>))}
                    </select>
                )} />
          </div>
          <div>
            <label htmlFor="virtual_agent_profile_id" className={labelClass}>Perfil de Agente Virtual</label>
            <Controller name="virtual_agent_profile_id" control={control}
                render={({ field }) => (
                    <select {...field} id="virtual_agent_profile_id" className={`${inputBaseClass} ${errors.virtual_agent_profile_id ? inputErrorClass : ''}`} disabled={isLoadingVAPs || !currentMainType}>
                        <option value="">{isLoadingVAPs ? "Cargando perfiles..." : (currentMainType ? "Ninguno (Usar directo del LLM)" : "Selecciona Tipo Principal")}</option>
                        {availableVAPs.map(vap => (<option key={vap.value} value={String(vap.value)}>{vap.label}</option>))}
                    </select>
                )} />
          </div>
           <div className="md:col-span-2 flex items-center pt-2">
              <input id="is_active" type="checkbox" {...register('is_active')} className={checkboxClass} /> 
              <label htmlFor="is_active" className="ml-2 text-sm font-medium text-gray-700 dark:text-gray-300 cursor-pointer select-none">Activo</label> 
          </div>
          <div className="md:col-span-2 flex items-center pt-2">
              <input id="is_public" type="checkbox" {...register('is_public')} className={checkboxClass} /> 
              <label htmlFor="is_public" className="ml-2 text-sm font-medium text-gray-700 dark:text-gray-300 cursor-pointer select-none">Público</label> 
          </div>
        </div>
      </section>

      {/* === SECCIÓN DE CONFIGURACIÓN ESPECÍFICA DEL TIPO === */}
      {currentMainType && (
          <section className={fieldGroupClass}>
              <div className="flex items-center">
                  {React.createElement(mainTypeOptions.find(o=>o.value === currentMainType)?.icon || InformationCircleIcon, {className: "h-6 w-6 mr-2 text-indigo-500 dark:text-indigo-400"})}
                  <h2 className={titleClass}>
                      Configuración: {mainTypeOptions.find(o=>o.value === currentMainType)?.label}
                  </h2>
              </div>
              
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
                const chunkSizeValue = getValues('processing_config_documental.chunk_size');
                
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

              {currentMainType === ContextMainType.DATABASE_QUERY && (
                <div className="space-y-4 pt-2">
                    <div>
                        <label htmlFor="db_connection_config_id" className={labelClass}>Conexión de Base de Datos <span className="text-red-500">*</span></label>
                         <Controller name="db_connection_config_id" control={control} rules={{ validate: value => (currentMainType === ContextMainType.DATABASE_QUERY && !value) ? "Se requiere una conexión." : true }}
                            render={({ field }) => (
                                <select {...field} id="db_connection_config_id" className={`${inputBaseClass} ${errors.db_connection_config_id ? inputErrorClass : ''}`} disabled={isLoadingDbConnections}>
                                    <option value="">{isLoadingDbConnections ? "Cargando conexiones..." : "-- Selecciona conexión --"}</option>
                                    {availableDbConnections.map(conn => (<option key={conn.value} value={String(conn.value)}>{conn.label}</option>))}
                                </select>
                            )} />
                        {errors.db_connection_config_id && <p className="mt-1 text-xs text-red-500">{errors.db_connection_config_id.message}</p>}
                    </div>
                    <div>
                      <label htmlFor="schema_info_type" className={labelClass}>Tipo de Información de Schema <span className="text-red-500">*</span></label>
                       {/* TODO: Hacerlo un Select si hay múltiples opciones */}
                      <input id="schema_info_type" type="text" {...register('processing_config_database_query.schema_info_type', {required: "Requerido"})} className={`${inputBaseClass} ${errors.processing_config_database_query?.schema_info_type ? inputErrorClass : ''}`} />
                      {errors.processing_config_database_query?.schema_info_type && <p className="mt-1 text-xs text-red-500">{errors.processing_config_database_query.schema_info_type.message}</p>}
                    </div>
                     <div>
                        <label htmlFor="selected_schema_tables_for_llm" className={labelClass}>Tablas de BD Seleccionadas para LLM (schema.tabla)</label>
                        <CreatableMultiSelect
                          name="processing_config_database_query.selected_schema_tables_for_llm" // El path en react-hook-form
                          control={control} // El objeto 'control' del useForm principal
                          id="selected_schema_tables_for_llm"
                          placeholder={isLoadingDbTables ? "Cargando tablas..." : "Selecciona o escribe tablas..."}
                          isDisabled={isLoadingDbTables || !watchedDbConnectionId}
                          options={dbSchemaTableOptions} // Tus opciones en formato {label, value}
                          // El componente interno CreatableMultiSelect se encargará de mapear el array de strings
                          // (que react-hook-form guarda para este campo) al formato de opciones {label, value}
                          // y viceversa, como definiste en su `render` con `field.value.map(...)` y `onChange(options.map(...))`.
                      />
                      {/* Para mostrar errores de este campo específico */}
                      {errors.processing_config_database_query?.selected_schema_tables_for_llm && 
                          <p className="mt-1 text-xs text-red-500">{errors.processing_config_database_query.selected_schema_tables_for_llm.message}</p>}
                        {errors.processing_config_database_query?.selected_schema_tables_for_llm && <p className="mt-1 text-xs text-red-500">{errors.processing_config_database_query.selected_schema_tables_for_llm.message}</p>}
                         <p className={formHelperTextClass}>Tablas que el LLM podrá "ver" para construir queries. Si está vacío, el LLM podría usar todas las tablas del "Diccionario de Tablas".</p>
                    </div>
                    <div>
                      <label htmlFor="dictionary_table_query" className={labelClass}>Query para Diccionario de Tablas (SQL Server Custom)</label>
                      <textarea id="dictionary_table_query" {...register('processing_config_database_query.dictionary_table_query')} rows={4} className={`${inputBaseClass}`} placeholder="SELECT s.name as table_schema, t.name as table_name, ..."/>
                      {errors.processing_config_database_query?.dictionary_table_query && <p className="mt-1 text-xs text-red-500">{errors.processing_config_database_query.dictionary_table_query.message}</p>}
                      {/* <Button type="button" variant="outline" size="sm" onClick={handleTestDictionaryQuery} isLoading={isTestingQuery} icon={<BeakerIcon className="h-4 w-4"/>} className="mt-2">Probar Query</Button> */}
                       {testQueryFeedback && <p className={`mt-2 text-xs p-2 rounded ${testQueryFeedback.type === 'success' ? 'bg-green-100 dark:bg-green-700 text-green-700 dark:text-green-100' : 'bg-red-100 dark:bg-red-700 text-red-700 dark:text-red-100'}`}>{testQueryFeedback.message}</p>}
                    </div>
                    <div>
                      <label htmlFor="custom_table_descriptions_json" className={labelClass}>Descripciones Personalizadas de Tablas (JSON)</label>
                      <textarea id="custom_table_descriptions_json" {...register('processing_config_database_query.custom_table_descriptions_json', { validate: value => { try { JSON.parse(value || '{}'); return true; } catch { return 'JSON inválido';}}})} rows={4} className={`${inputBaseClass} font-mono text-xs ${errors.processing_config_database_query?.custom_table_descriptions_json ? inputErrorClass : ''}`} placeholder='{\n  "esquema.tabla_nombre": "Descripción para LLM...",\n  "public.clientes": "Información de clientes de la empresa."\n}'/>
                      {errors.processing_config_database_query?.custom_table_descriptions_json && <p className="mt-1 text-xs text-red-500">{errors.processing_config_database_query.custom_table_descriptions_json.message}</p>}
                    </div>
                     <div className={gridLayout}>
                        <div>
                            <label htmlFor="db_schema_chunk_size" className={labelClass}>Tamaño Chunk Schema BD <span className="text-red-500">*</span></label>
                            <input id="db_schema_chunk_size" type="number" {...register('processing_config_database_query.db_schema_chunk_size', {valueAsNumber:true, required:true, min:100})} className={`${inputBaseClass} ${errors.processing_config_database_query?.db_schema_chunk_size ? inputErrorClass : ''}`}/>
                            {errors.processing_config_database_query?.db_schema_chunk_size && <p className="mt-1 text-xs text-red-500">{errors.processing_config_database_query.db_schema_chunk_size.message}</p>}
                        </div>
                        <div>
                            <label htmlFor="db_schema_chunk_overlap" className={labelClass}>Solapamiento Chunk Schema BD <span className="text-red-500">*</span></label>
                            <input id="db_schema_chunk_overlap" type="number" {...register('processing_config_database_query.db_schema_chunk_overlap', {valueAsNumber:true, required:true, min:0})} className={`${inputBaseClass} ${errors.processing_config_database_query?.db_schema_chunk_overlap ? inputErrorClass : ''}`}/>
                            {errors.processing_config_database_query?.db_schema_chunk_overlap && <p className="mt-1 text-xs text-red-500">{errors.processing_config_database_query.db_schema_chunk_overlap.message}</p>}
                        </div>
                    </div>

                    {/* --- Sub-sección SQL Select Policy --- */}
                    <div className="pt-3">
                      <button type="button" onClick={() => setIsSqlPolicyExpanded(!isSqlPolicyExpanded)} className={toggleButtonClass}>
                        {isSqlPolicyExpanded ? <ChevronUpIcon className="h-5 w-5 mr-1" /> : <ChevronDownIcon className="h-5 w-5 mr-1" />}
                        Configurar Política de Selección SQL (Avanzado)
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
                            <Button type="button" variant="outline" size="sm" onClick={addColumnAccessRuleItem} icon={<PlusCircleIcon className="h-5 w-5"/>} className="mt-2">
                                Añadir Regla de Tabla
                            </Button>
                          </div>
                        </div>
                      )}
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
