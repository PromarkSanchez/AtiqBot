// src/components/admin/api_clients/ApiClientForm.tsx
import React, { useEffect } from 'react';
import { useForm, Controller, type SubmitHandler } from 'react-hook-form';
import type {
  ApiClientResponse,
  ApiClientCreate,
  ApiClientUpdate,
  ApiClientSettingsSchema,
  ContextDefinitionResponse,
  LLMModelConfigResponse,
  VirtualAgentProfileResponse,
  HumanAgentGroupResponse,
} from '../../../services/api/schemas'; // Tus importaciones de schemas parecen correctas

import {
  useReadAllContextDefinitionsEndpointApiV1AdminContextDefinitionsGet,
  useReadAllLlmModelConfigsApiV1AdminLlmModelsGet as  useReadAllLlmModelConfigsLlmModelsGet,
  useReadAllVirtualAgentProfilesApiV1AdminVirtualAgentProfilesGet as useReadAllVirtualAgentProfilesVirtualAgentProfilesGet,
  useReadAllHumanAgentGroupsEndpointApiV1HumanAgentGroupsHumanAgentGroupsGet as useReadAllHumanAgentGroupsEndpointHumanAgentGroupsGet,
} from '../../../services/api/endpoints';

import CreatableMultiSelect from '../../shared/forms/CreatableMultiSelect'; // Importado y usado

// Tipos para el formulario, directamente basados en los schemas de Orval.
// Para `ApiClientCreate`, `settings` es opcional, pero lo incluimos para consistencia
// y `defaultValues` se encargará de la inicialización.
type FormDataType = Omit<ApiClientCreate, 'settings'> & {
  settings: Partial<ApiClientSettingsSchema>; 
};

interface ApiClientFormProps {
  apiClient?: ApiClientResponse | null;
  onFormSubmit: (data: ApiClientCreate | ApiClientUpdate) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  isEditMode: boolean;
}

const ApiClientForm: React.FC<ApiClientFormProps> = ({
  apiClient,
  onFormSubmit,
  onCancel,
  isSubmitting,
  isEditMode,
}) => {
  const {
    register,
    handleSubmit,
    reset,
    control,
    watch,
    formState: { errors, isDirty, touchedFields }, // `touchedFields` es útil
  } = useForm<FormDataType>({
    mode: 'onChange',
    defaultValues: { // Los valores por defecto deben coincidir con `FormDataType`
      name: '',
      description: null,
      is_active: true,
      settings: { // Inicializa settings, Pydantic en backend usará sus defaults si no se envían aquí
        application_id: '', // Requerido
        allowed_context_ids: [], // Default a lista vacía
        is_web_client: false,    // Default a false
        allowed_web_origins: [], // Default a lista vacía
        human_handoff_agent_group_id: null, // Todos los IDs override opcionales a null
        default_llm_model_config_id_override: null,
        default_virtual_agent_profile_id_override: null,
        history_k_messages: 5,   // Un default sensato, Pydantic schema debe tener un default también
        max_tokens_per_response_override: null,
      },
    },
  });

  const isWebClientWatched = watch('settings.is_web_client');

  // --- Carga de datos para Selects ---
  const { data: contextDefinitionsResponse, isLoading: isLoadingContexts } =
    useReadAllContextDefinitionsEndpointApiV1AdminContextDefinitionsGet(
      { limit: 1000 }, { query: { queryKey: ['allContextDefinitionsForApiClientForm'], staleTime: 300000 } }
    );
  const availableContexts: ContextDefinitionResponse[] = contextDefinitionsResponse || [];

  const { data: llmModelConfigsResponse, isLoading: isLoadingLLMConfigs } =
    useReadAllLlmModelConfigsLlmModelsGet( // Asumiendo que está en /api/v1/admin/llm-model-configs
      { limit: 100 }, { query: { queryKey: ['allLlmModelConfigs'], staleTime: 300000 } }
    );
  const availableLlmConfigs: LLMModelConfigResponse[] = llmModelConfigsResponse || [];

  const { data: virtualAgentProfilesResponse, isLoading: isLoadingVAPs } =
    useReadAllVirtualAgentProfilesVirtualAgentProfilesGet( // Asumiendo que está en /api/v1/admin/virtual-agent-profiles
      { limit: 100 }, { query: { queryKey: ['allVirtualAgentProfiles'], staleTime: 300000 } }
    );
  const availableVAPs: VirtualAgentProfileResponse[] = virtualAgentProfilesResponse || [];
  
  const { data: humanAgentGroupsResponse, isLoading: isLoadingHAGroups } =
    useReadAllHumanAgentGroupsEndpointHumanAgentGroupsGet( // Asumiendo que está en /api/v1/admin/human-agent-groups
      { limit: 100 }, { query: { queryKey: ['allHumanAgentGroups'], staleTime: 300000 } }
    );
  const availableHAGroups: HumanAgentGroupResponse[] = humanAgentGroupsResponse || [];

  // --- Efecto para popular el formulario ---
  useEffect(() => {
    if (isEditMode && apiClient) {
      // Mapear la respuesta del API (ApiClientResponse) a la estructura del formulario (FormDataType)
      // especialmente el objeto 'settings'.
      const currentSettings = apiClient.settings;
      reset({
        name: apiClient.name || '',
        description: apiClient.description || null,
        is_active: apiClient.is_active !== undefined ? apiClient.is_active : true,
        settings: { // Asegúrate que todos los campos de ApiClientSettingsSchema (form) estén aquí
          application_id: currentSettings?.application_id || '',
          allowed_context_ids: currentSettings?.allowed_context_ids || [],
          is_web_client: currentSettings?.is_web_client || false,
          allowed_web_origins: currentSettings?.allowed_web_origins || [],
          human_handoff_agent_group_id: currentSettings?.human_handoff_agent_group_id ?? null,
          default_llm_model_config_id_override: currentSettings?.default_llm_model_config_id_override ?? null,
          default_virtual_agent_profile_id_override: currentSettings?.default_virtual_agent_profile_id_override ?? null,
          history_k_messages: currentSettings?.history_k_messages ?? 5,
          max_tokens_per_response_override: currentSettings?.max_tokens_per_response_override ?? null,
        },
      });
    } else if (!isEditMode) { // Resetea a los valores por defecto definidos en useForm
      reset(); // Esto usará los defaultValues de useForm
    }
  }, [apiClient, isEditMode, reset]);

  // --- Lógica de Submit ---
  const processSubmit: SubmitHandler<FormDataType> = (formData) => {
    // formData ya debería tener 'settings' como un objeto.
    // Convertimos campos numéricos que podrían ser strings vacíos a null o number.
    const parsedSettings: ApiClientSettingsSchema = {
        //application_id: formData.settings.application_id.trim(), // Requerido
        application_id: (formData.settings?.application_id || '').trim(), // Requerido

        // Los opcionales se manejan así: si formData.settings.nombreCampo existe, se usa. Si no, undefined (y Pydantic usa su default).
        // Si el campo está vacío (ej, select sin selección para un opcional), se convierte a null.
        allowed_context_ids: formData.settings.allowed_context_ids || [],
        is_web_client: formData.settings.is_web_client || false, // schema lo define opcional con default false
        allowed_web_origins: formData.settings.allowed_web_origins || [],
        
        human_handoff_agent_group_id: formData.settings.human_handoff_agent_group_id ? Number(formData.settings.human_handoff_agent_group_id) : null,
        default_llm_model_config_id_override: formData.settings.default_llm_model_config_id_override ? Number(formData.settings.default_llm_model_config_id_override) : null,
        default_virtual_agent_profile_id_override: formData.settings.default_virtual_agent_profile_id_override ? Number(formData.settings.default_virtual_agent_profile_id_override) : null,
        
        history_k_messages: Number(formData.settings.history_k_messages), // Si el schema dice ?number, entonces este está bien. Si no es opcional, debe tener valor.
        
        max_tokens_per_response_override: formData.settings.max_tokens_per_response_override ? Number(formData.settings.max_tokens_per_response_override) : null,
    };
    
    const finalPayload: ApiClientCreate | ApiClientUpdate = {
      name: formData.name.trim(),
      description: formData.description ? formData.description.trim() : null, // string vacía a null
      is_active: formData.is_active,
      settings: parsedSettings, // Pasa el objeto settings completo.
    };
    
    onFormSubmit(finalPayload);
  };

  // Clases Tailwind (sin cambios de la versión anterior)
  const labelClass = "block text-sm font-medium text-gray-700 dark:text-gray-300";
  const inputBaseClass = "mt-1 block w-full px-3 py-2 border rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-slate-800 dark:text-white disabled:bg-gray-100 dark:disabled:bg-slate-700";
  const inputNormalClass = "border-gray-300 dark:border-gray-600";
  const inputErrorClass = "border-red-500 dark:border-red-400 focus:ring-red-500 focus:border-red-500";
  const checkboxClass = "focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300 dark:border-gray-600 rounded bg-gray-100 dark:bg-gray-700 checked:bg-indigo-500 dark:checked:bg-indigo-500";
  const btnSecondaryClass = "px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-slate-700 border border-gray-300 dark:border-slate-600 rounded-md hover:bg-gray-50 dark:hover:bg-slate-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70";
  const btnPrimaryClass = "px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 border border-transparent rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70 disabled:cursor-not-allowed";
  const selectClass = `${inputBaseClass} ${inputNormalClass}`; // Para los <select>

  return (
    <form onSubmit={handleSubmit(processSubmit)}>
      <div className="space-y-6 p-1">
        {/* --- Campos Principales (Name, Description, Is Active) --- */}
        <div>
          <label htmlFor="api_client_name" className={labelClass}>Nombre Cliente API <span className="text-red-500">*</span></label>
          <input id="api_client_name" type="text" 
            {...register('name', { 
              required: 'El nombre es obligatorio.', 
              minLength: {value: 3, message: "Mínimo 3 caracteres"},
            })}
            className={`${inputBaseClass} ${errors.name ? inputErrorClass : inputNormalClass}`} />
          {errors.name && <p className="mt-1 text-xs text-red-500">{errors.name.message}</p>}
        </div>
        <div>
          <label htmlFor="api_client_description" className={labelClass}>Descripción</label>
          <textarea id="api_client_description" rows={2} 
            {...register('description')}
            className={`${inputBaseClass} ${inputNormalClass}`} />
            {/* react-hook-form no necesita error específico para textarea opcional a menos que haya una validación */}
        </div>
        <div className="flex items-start">
          <div className="flex items-center h-5"><input id="api_client_is_active" type="checkbox" {...register('is_active')} className={checkboxClass} /></div>
          <div className="ml-3 text-sm">
            <label htmlFor="api_client_is_active" className="font-medium text-gray-700 dark:text-gray-300 select-none">Cliente Activo</label>
          </div>
        </div>

        <hr className="my-4 border-gray-300 dark:border-gray-600" />
        <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">
          Configuraciones Específicas (Settings)
        </h3>
        
        {/* --- Contenedor de Settings --- */}
        <div className="space-y-4 p-3 border dark:border-gray-700 rounded-md bg-gray-50 dark:bg-slate-800/30">
          
          {/* settings.application_id */}
          <div>
            <label htmlFor="settings_application_id" className={`${labelClass} mb-1`}>
              ID Aplicación (X-Application-ID) <span className="text-red-500">*</span>
            </label>
            <input id="settings_application_id" type="text" 
              {...register('settings.application_id', { required: "ID de Aplicación es obligatorio." })}
              className={`${inputBaseClass} ${errors.settings?.application_id ? inputErrorClass : inputNormalClass}`} 
              placeholder="Ej: WEB_CHAT_EMPRESA_V2" />
            {errors.settings?.application_id && <p className="mt-1 text-xs text-red-500">{errors.settings.application_id.message}</p>}
          </div>

          {/* settings.allowed_context_ids */}
          <div>
            <label className={`${labelClass} mb-1`}>Contextos Permitidos</label>
            {isLoadingContexts ? (<p className="text-sm animate-pulse dark:text-gray-400">Cargando contextos...</p>) :
              availableContexts.length > 0 ? (
                <div className="space-y-1 p-2 border rounded max-h-48 overflow-y-auto bg-white dark:bg-slate-700 dark:border-gray-600">
                  <Controller
                    name="settings.allowed_context_ids"
                    control={control}
                    defaultValue={[]} // Asegura que es un array
                    render={({ field }) => (
                      <>
                        {availableContexts.map((context) => (
                          <div key={context.id} className="flex items-center py-0.5">
                            <input id={`context-for-client-${context.id}`} type="checkbox" value={context.id}
                              checked={field.value?.includes(context.id)}
                              onChange={(e) => {
                                const contextId = Number(e.target.value);
                                const currentValues = Array.isArray(field.value) ? field.value : [];
                                const newValues = e.target.checked 
                                  ? [...currentValues, contextId] 
                                  : currentValues.filter((id) => id !== contextId);
                                field.onChange(newValues);
                              }}
                              className={`${checkboxClass} mr-2`}
                            />
                            <label htmlFor={`context-for-client-${context.id}`} className="text-sm dark:text-gray-200 select-none cursor-pointer">
                              {context.name} <span className="text-xs text-gray-500 dark:text-gray-400">({context.main_type})</span>
                            </label>
                          </div>
                        ))}
                      </>
                    )}
                  />
                </div>
              ) : (<p className="text-sm text-gray-500 dark:text-gray-400">No hay Contextos definidos.</p>)
            }
            {errors.settings?.allowed_context_ids && <p className="mt-1 text-xs text-red-500">{typeof errors.settings.allowed_context_ids.message === 'string' ? errors.settings.allowed_context_ids.message : 'Error en contextos'}</p>}
          </div>

          {/* Grid para history_k_messages y max_tokens_per_response_override */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-4">
            {/* settings.history_k_messages */}
            <div>
                <label htmlFor="settings_history_k_messages" className={`${labelClass} mb-1`}>Mensajes Historial (k) <span className="text-red-500">*</span></label>
                <input id="settings_history_k_messages" type="number" 
                  {...register('settings.history_k_messages', { 
                      setValueAs: v => (v === "" || v === null || v === undefined) ? 0 : Number(v), // Si vacío, 0 (como dice Pydantic schema history_k_messages: int = 5), o el valor que tenga tu schema como default no opcional
                      required: "Nº mensajes de historial es obligatorio (mín 0).",
                      min: { value: 0, message: "Mínimo 0" },
                      validate: v => (!isNaN(parseFloat(String(v))) && Number(v) >= 0) || "Debe ser un número >= 0"
                  })} 
                  className={`${inputBaseClass} ${errors.settings?.history_k_messages ? inputErrorClass : inputNormalClass}`} />
                {errors.settings?.history_k_messages && <p className="text-xs text-red-500">{errors.settings.history_k_messages.message}</p>}
            </div>
            {/* settings.max_tokens_per_response_override */}
            <div>
                <label htmlFor="settings_max_tokens_per_response_override" className={`${labelClass} mb-1`}>Max Tokens Respuesta (Override)</label>
                <input id="settings_max_tokens_per_response_override" type="number" 
                  {...register('settings.max_tokens_per_response_override', { 
                    setValueAs: v => (v === "" || v === null || v === undefined) ? null : Number(v),
                    validate: value => value === null || (typeof value === 'number' && !isNaN(value) && value >= 1) || "Debe ser un número positivo >= 1 o vacío"
                  })} 
                  className={`${inputBaseClass} ${errors.settings?.max_tokens_per_response_override ? inputErrorClass : inputNormalClass}`} 
                  placeholder="Vacío para no sobrescribir"
                />
                {errors.settings?.max_tokens_per_response_override && <p className="text-xs text-red-500">{errors.settings.max_tokens_per_response_override.message}</p>}
            </div>
          </div>
          
          {/* settings.is_web_client */}
          <div className="pt-2">
            <div className="flex items-start">
              <div className="flex items-center h-5">
                <input id="settings_is_web_client" type="checkbox" 
                {...register('settings.is_web_client')} 
                className={checkboxClass}/>
              </div>
              <div className="ml-3 text-sm">
                <label htmlFor="settings_is_web_client" className="font-medium text-gray-700 dark:text-gray-300 select-none">Es Cliente Web (Activar CORS)</label>
              </div>
            </div>
          </div>

          {/* settings.allowed_web_origins */}
          <div className={`${isWebClientWatched ? 'opacity-100' : 'opacity-50'}`}>
            <label htmlFor="creatable-multi-select-web-origins" className={`${labelClass} mb-1`}>Orígenes Web Permitidos (CORS)</label>
            <CreatableMultiSelect // Usando tu componente CreatableMultiSelect
                name="settings.allowed_web_origins"
                control={control}
                id="creatable-multi-select-web-origins" // ID único para el select
                placeholder="Añadir origen (ej: https://miapp.com) y Enter"
                isLoading={isSubmitting} // Puede ser
                // `options` puede ser omitido si no tienes predefinidos. Tu CreatableMultiSelect debería manejar esto.
                // Tu componente CreatableMultiSelect ya maneja el mapeo de `field.value` string[] a Option[] y viceversa.
                label="" // El label ya está puesto arriba
            />
            {!isWebClientWatched && <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Activa "Es Cliente Web" para configurar.</p>}
            {errors.settings?.allowed_web_origins && <p className="mt-1 text-xs text-red-500">{typeof errors.settings.allowed_web_origins.message === 'string' ? errors.settings.allowed_web_origins.message : 'Error en orígenes web'}</p>}
          </div>
          
          {/* Grid para override selects */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
            {/* settings.human_handoff_agent_group_id */}
            <div>
                <label htmlFor="settings_human_handoff_agent_group_id" className={labelClass}>Grupo Handoff (Override)</label>
                <Controller
                    name="settings.human_handoff_agent_group_id"
                    control={control}
                    defaultValue={null}
                    render={({ field }) => (
                        <select
                            id="settings_human_handoff_agent_group_id"
                            {...field}
                            onChange={e => field.onChange(e.target.value ? Number(e.target.value) : null)}
                            value={field.value ?? ''} // Si es null/undefined, value="" para que el placeholder del select funcione
                            className={`${selectClass} ${errors.settings?.human_handoff_agent_group_id ? inputErrorClass : ''}`}
                            disabled={isLoadingHAGroups || isSubmitting}
                        >
                            <option value="">{isLoadingHAGroups ? 'Cargando...' : 'Ninguno'}</option>
                            {availableHAGroups.map(group => (
                                <option key={group.id} value={group.id}>{group.name} (ID: {group.id})</option>
                            ))}
                        </select>
                    )}
                />
                {errors.settings?.human_handoff_agent_group_id && <p className="text-xs text-red-500">{typeof errors.settings.human_handoff_agent_group_id.message === 'string' ? errors.settings.human_handoff_agent_group_id.message : 'Error en grupo handoff'}</p>}
            </div>

            {/* settings.default_llm_model_config_id_override */}
            <div>
                <label htmlFor="settings_default_llm_model_config_id_override" className={labelClass}>Config LLM (Override)</label>
                 <Controller
                    name="settings.default_llm_model_config_id_override"
                    control={control}
                    defaultValue={null}
                    render={({ field }) => (
                        <select
                            id="settings_default_llm_model_config_id_override"
                            {...field}
                            onChange={e => field.onChange(e.target.value ? Number(e.target.value) : null)}
                            value={field.value ?? ''}
                            className={`${selectClass} ${errors.settings?.default_llm_model_config_id_override ? inputErrorClass : ''}`}
                            disabled={isLoadingLLMConfigs || isSubmitting}
                        >
                            <option value="">{isLoadingLLMConfigs ? 'Cargando...' : 'Ninguno'}</option>
                            {/* Corregido a display_name según tu schema LLMModelConfigResponse */}
                            {availableLlmConfigs.map(config => (
                                <option key={config.id} value={config.id}>{config.display_name} (ID: {config.id})</option>
                            ))}
                        </select>
                    )}
                />
                {errors.settings?.default_llm_model_config_id_override && <p className="text-xs text-red-500">{typeof errors.settings.default_llm_model_config_id_override.message === 'string' ? errors.settings.default_llm_model_config_id_override.message : 'Error en LLM override'}</p>}
            </div>

            {/* settings.default_virtual_agent_profile_id_override */}
            <div>
                <label htmlFor="settings_default_virtual_agent_profile_id_override" className={labelClass}>Perfil Agente Virtual (Override)</label>
                <Controller
                    name="settings.default_virtual_agent_profile_id_override"
                    control={control}
                    defaultValue={null}
                    render={({ field }) => (
                        <select
                            id="settings_default_virtual_agent_profile_id_override"
                            {...field}
                            onChange={e => field.onChange(e.target.value ? Number(e.target.value) : null)}
                            value={field.value ?? ''}
                            className={`${selectClass} ${errors.settings?.default_virtual_agent_profile_id_override ? inputErrorClass : ''}`}
                            disabled={isLoadingVAPs || isSubmitting}
                        >
                            <option value="">{isLoadingVAPs ? 'Cargando...' : 'Ninguno'}</option>
                            {availableVAPs.map(profile => (
                                <option key={profile.id} value={profile.id}>{profile.name} (ID: {profile.id})</option>
                            ))}
                        </select>
                    )}
                />
                {errors.settings?.default_virtual_agent_profile_id_override && <p className="text-xs text-red-500">{typeof errors.settings.default_virtual_agent_profile_id_override.message === 'string' ? errors.settings.default_virtual_agent_profile_id_override.message : 'Error en perfil virtual override'}</p>}
            </div>
          </div> {/* Fin Grid para override selects */}
        </div> {/* Fin Contenedor de Settings */}
      </div> {/* Fin Contenedor Principal del Formulario */}

      {/* --- Botones de Acción --- */}
      <div className="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700 flex justify-end space-x-3">
        <button type="button" onClick={onCancel} disabled={isSubmitting} className={btnSecondaryClass}>Cancelar</button>
        <button type="submit" 
          disabled={isSubmitting || (!isDirty && isEditMode && Object.keys(touchedFields).length === 0) } 
          className={btnPrimaryClass}>
          {isSubmitting ? 'Guardando...' : (isEditMode ? 'Guardar Cambios' : 'Crear Cliente API')}
        </button>
      </div>
    </form>
  );
};
export default ApiClientForm;