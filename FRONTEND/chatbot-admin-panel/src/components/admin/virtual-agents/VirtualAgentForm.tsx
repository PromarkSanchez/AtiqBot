// src/components/admin/virtual-agents/VirtualAgentForm.tsx

import React, { useEffect } from 'react';
import { useForm, type SubmitHandler } from 'react-hook-form';
import toast from 'react-hot-toast';

import type { 
    VirtualAgentProfileResponse,
    VirtualAgentProfileCreate,
} from '../../../services/api/schemas';
import { 
    useReadAllLlmModelConfigsApiV1AdminLlmModelsGet as useGetAllModels,
    useGenerateOptimizedPromptEndpointApiV1AdminVirtualAgentProfilesGeneratePromptPost as useGeneratePrompt,
} from '../../../services/api/endpoints';
import { Button } from '../../shared/Button';
import { SparklesIcon } from '@heroicons/react/24/solid';

// El tipo ahora NO incluye 'user_provided_goal_description' y AÑADE los campos de la Ficha.
type VirtualAgentFormValues = Omit<VirtualAgentProfileCreate, 'llm_model_config_id' | 'temperature_override' | 'max_tokens_override' | 'user_provided_goal_description'> & {
    llm_model_config_id: string;
    temperature_override?: number | string | null;
    max_tokens_override?: number | string | null;
    // Campos para la "Ficha de Personaje" que el usuario llenará en la UI
    ficha_nombre_agente: string;
    ficha_rol_principal: string;
    ficha_personalidad_tono: string;
    ficha_dominio_conocimiento: string;
    ficha_reglas_adicionales?: string;
};


interface VirtualAgentFormProps {
  agent?: VirtualAgentProfileResponse | null;
  onFormSubmit: (data: VirtualAgentProfileCreate) => void;
  onCancel: () => void;
  isSubmitting: boolean;
}

const VirtualAgentForm: React.FC<VirtualAgentFormProps> = ({ agent, onFormSubmit, onCancel, isSubmitting }) => {
  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors },
  } = useForm<VirtualAgentFormValues>({
    defaultValues: {
        name: '',
        description: '',
        // user_provided_goal_description se elimina
        greeting_prompt: '',
        name_confirmation_prompt: '',
        system_prompt: '',
        is_active: true,
        llm_model_config_id: '',
        temperature_override: null,
        max_tokens_override: null,
        // Inicializamos los nuevos campos de la ficha
        ficha_nombre_agente: '', ficha_rol_principal: '', ficha_personalidad_tono: '',
        ficha_dominio_conocimiento: '', ficha_reglas_adicionales: '',
    },
  });
  
  const { data: modelsData, isLoading: isLoadingModels } = useGetAllModels({ limit: 1000, only_active: true });
  const generatePromptMutation = useGeneratePrompt();
  const activeModels = modelsData || [];
  
  useEffect(() => {
    if (agent) {
      // MODO EDICIÓN
      const sheet = agent.character_sheet_json as any || {};
      reset({
        ...agent,
        llm_model_config_id: agent.llm_model_config_id.toString(),
        // Rellenamos los campos de la ficha desde el JSON guardado
        ficha_nombre_agente: sheet.nombre_agente || '',
        ficha_rol_principal: sheet.rol_principal || '',
        ficha_personalidad_tono: sheet.personalidad_tono || '',
        ficha_dominio_conocimiento: sheet.dominio_conocimiento || '',
        ficha_reglas_adicionales: sheet.reglas_adicionales || '',
      });
    } else {
      // MODO CREACIÓN
      reset();
    }
  }, [agent, reset]);
  // ---> FIN DEL CAMBIO <---


  const handleGeneratePrompt = async () => {
    const llmId = watch('llm_model_config_id');
    const { ficha_nombre_agente, ficha_rol_principal, ficha_personalidad_tono, ficha_dominio_conocimiento, ficha_reglas_adicionales } = watch();

    if (!ficha_rol_principal || !ficha_dominio_conocimiento || !llmId) {
      toast.error('Por favor, completa al menos el "Rol Principal", "Dominio" y selecciona un Modelo LLM para usar el asistente.');
      return;
    }
    
    // CONSTRUIMOS EL user_description A PARTIR DE LOS CAMPOS ESTRUCTURADOS, eliminando el antiguo campo 'goal'
    const userDescription = `---FICHA DE PERSONAJE---
    NOMBRE_AGENTE: ${ficha_nombre_agente || "Asistente Virtual"}
    ROL_PRINCIPAL: ${ficha_rol_principal}
    PERSONALIDAD_TONO:
    ${ficha_personalidad_tono || "- Tono neutro y servicial."}
    DOMINIO_CONOCIMIENTO_ESTRICTO:
    ${ficha_dominio_conocimiento}
    REGLA_ADICIONAL_IMPORTANTE:
    ${ficha_reglas_adicionales || "Ninguna."}`.trim();

    toast.loading('Generando prompts con IA...', { id: 'generating-prompt' });
    generatePromptMutation.mutate(
      { data: { user_description: userDescription, llm_model_config_id: parseInt(llmId) } },
      {
        onSuccess: (promptDict) => {
          toast.success('¡Conjunto de prompts generado!', { id: 'generating-prompt' });
          setValue('greeting_prompt', promptDict.greeting_prompt || '', { shouldDirty: true });
          setValue('name_confirmation_prompt', promptDict.name_confirmation_prompt || '', { shouldDirty: true });
          setValue('system_prompt', promptDict.system_prompt || '', { shouldDirty: true });
        },
        onError: (error: any) => { /* Tu manejador de errores original está bien */ }
      }
    );
  };
  

  const processSubmit: SubmitHandler<VirtualAgentFormValues> = (data) => {
    // Excluimos los campos 'ficha_*' antes de enviar a la BD
    const { ficha_nombre_agente, ficha_rol_principal, ficha_personalidad_tono, ficha_dominio_conocimiento, ficha_reglas_adicionales, ...restOfData } = data;
    
    const tempOverride = restOfData.temperature_override;
    const tokensOverride = restOfData.max_tokens_override;
    
    // Guardamos un resumen en `user_provided_goal_description` para referencia futura
    const goalDescriptionFromFicha = `Rol: ${ficha_rol_principal}. Dominio: ${ficha_dominio_conocimiento}`;
    const characterSheet = {
      nombre_agente: ficha_nombre_agente,
      rol_principal: ficha_rol_principal,
      personalidad_tono: ficha_personalidad_tono,
      dominio_conocimiento: ficha_dominio_conocimiento,
      reglas_adicionales: ficha_reglas_adicionales
    };
    const goalDescription = `Rol: ${ficha_rol_principal}. Dominio: ${ficha_dominio_conocimiento}`;

    const payload: VirtualAgentProfileCreate = {
        ...restOfData,
        user_provided_goal_description: goalDescriptionFromFicha,
        character_sheet_json: characterSheet, // ¡El objeto completo!
        llm_model_config_id: parseInt(restOfData.llm_model_config_id),
        temperature_override: (tempOverride === '' || tempOverride === null || tempOverride === undefined) ? null : Number(tempOverride),
        max_tokens_override: (tokensOverride === '' || tokensOverride === null || tokensOverride === undefined) ? null : Number(tokensOverride),
    };
    
    onFormSubmit(payload);
  };
  
  const isGeneratingPrompt = generatePromptMutation.isPending;

  const inputStyle = (hasError: boolean) => `mt-1 block w-full px-3 py-2 border ${hasError ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900`;
  const selectStyle = (hasError: boolean) => `mt-1 block w-full pl-3 pr-10 py-2 border ${hasError ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md text-gray-900 dark:text-white bg-white dark:bg-gray-900`;
  const errorTextStyle = "mt-1 text-xs text-red-500 dark:text-red-400";
  const labelStyle = "block text-sm font-medium text-gray-700 dark:text-gray-300";


  return (
    <form onSubmit={handleSubmit(processSubmit)} noValidate>
      <div className="space-y-6 max-h-[75vh] overflow-y-auto p-1 pr-4">
        
        {/* --- Fila 1: Nombre y Modelo LLM Base --- */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
          <div>
            <label htmlFor="name" className={labelStyle}>Nombre del Agente <span className="text-red-500">*</span></label>
            <input
              id="name" type="text"
              {...register('name', { required: 'El nombre es obligatorio.' })}
              className={inputStyle(!!errors.name)}
            />
            {errors.name && <p className={errorTextStyle}>{errors.name.message}</p>}
          </div>
          <div>
            <label htmlFor="llm_model_config_id" className={labelStyle}>Modelo LLM Generador <span className="text-red-500">*</span></label>
            <select
              id="llm_model_config_id"
              {...register('llm_model_config_id', { required: 'Debes seleccionar un modelo.' })}
              className={selectStyle(!!errors.llm_model_config_id)}
              disabled={isLoadingModels}
            >
              <option value="">{isLoadingModels ? 'Cargando modelos...' : 'Selecciona un modelo'}</option>
              {activeModels.map((m) => (
                <option key={m.id} value={m.id}>{m.display_name} ({m.provider})</option>
              ))}
            </select>
            {errors.llm_model_config_id && <p className={errorTextStyle}>{errors.llm_model_config_id.message}</p>}
          </div>
        </div>

        {/* --- Descripción Interna --- */}
        <div>
            <label htmlFor="description" className={labelStyle}>Descripción interna (Opcional)</label>
            <input
              id="description" type="text"
              {...register('description')}
              placeholder="Ej: Agente para consultas académicas"
              className={inputStyle(false)}
            />
        </div>
        
        {/* --- SECCIÓN UNIFICADA Y SIMPLIFICADA DEL ASISTENTE --- */}
        <div className="pt-5 mt-5 border-t border-gray-200 dark:border-slate-700 space-y-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Asistente de Creación de Agente</h3>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">Rellena la "Ficha de Personaje" de tu agente. Luego, usa la IA para generar los 3 prompts automáticamente.</p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6">
                <div>
                    <label htmlFor="ficha_nombre_agente" className={labelStyle}>1. Nombre del Personaje (Ej: BiblioBot)</label>
                    <input id="ficha_nombre_agente" {...register('ficha_nombre_agente')} className={inputStyle(false)} />
                </div>
            </div>

            <div>
                <label htmlFor="ficha_rol_principal" className={labelStyle}>2. Rol Principal <span className="text-red-500">*</span></label>
                <textarea id="ficha_rol_principal" rows={2} {...register('ficha_rol_principal', {required: true})} placeholder="Ej: Asistente experto para la Biblioteca Central." className={inputStyle(!!errors.ficha_rol_principal)} />
            </div>

            <div>
                <label htmlFor="ficha_personalidad_tono" className={labelStyle}>3. Personalidad y Tono</label>
                <textarea id="ficha_personalidad_tono" rows={3} {...register('ficha_personalidad_tono')} placeholder={"Ej:\n- Tono: Formal pero amigable y servicial.\n- Personalidad: Preciso, paciente.\n- Toque especial: Usa el emoji 📚."} className={inputStyle(false)} />
            </div>
            
            <div>
                <label htmlFor="ficha_dominio_conocimiento" className={labelStyle}>4. Dominio de Conocimiento (Qué SÍ puede hacer) <span className="text-red-500">*</span></label>
                <textarea id="ficha_dominio_conocimiento" rows={3} {...register('ficha_dominio_conocimiento', {required: true})} placeholder={"Enumera las tareas que el bot PUEDE hacer. Ej:\n- Proporcionar horarios de la biblioteca.\n- Explicar conceptos del sílabo de un curso.\n- Responder preguntas sobre la política de vacaciones."} className={inputStyle(!!errors.ficha_dominio_conocimiento)} />
            </div>

             <div>
                <label htmlFor="ficha_reglas_adicionales" className={labelStyle}>5. Reglas Adicionales Importantes (Opcional)</label>
                <textarea id="ficha_reglas_adicionales" rows={2} {...register('ficha_reglas_adicionales')} 
                placeholder={"Define límites o comportamientos especiales. Ej:\n- Nunca confirmar disponibilidad, solo guiar al catálogo. \n- No dar opiniones personales sobre los cursos.\n- Siempre terminar la conversación ofreciendo ayuda adicional."} className={inputStyle(false)} />
            </div>

             <div className="mt-4 text-center">
                 <Button type="button" onClick={handleGeneratePrompt} isLoading={isGeneratingPrompt} disabled={isSubmitting} icon={<SparklesIcon className="h-5 w-5"/>}>
                     6. Generar Prompts con IA
                 </Button>
            </div>

             <div className="mt-6 border-t border-dashed pt-4 border-gray-300 dark:border-slate-600">
                <h4 className="text-md font-medium text-gray-800 dark:text-gray-200">Resultados Generados (Editables)</h4>
                 <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
                    <div>
                         <label htmlFor="greeting_prompt" className={labelStyle}>Prompt de Saludo</label>
                        <textarea id="greeting_prompt" rows={4} {...register('greeting_prompt')} className={`${inputStyle(false)} font-mono text-xs`} />
                    </div>
                     <div>
                         <label htmlFor="name_confirmation_prompt" className={labelStyle}>Prompt de Confirmación</label>
                        <textarea id="name_confirmation_prompt" rows={4} {...register('name_confirmation_prompt')} className={`${inputStyle(false)} font-mono text-xs`}/>
                    </div>
                </div>
                <div className="mt-4">
                     <label htmlFor="system_prompt" className={labelStyle}>System Prompt Principal <span className="text-red-500">*</span></label>
                    <textarea id="system_prompt" rows={12} {...register('system_prompt', { required: 'El System Prompt es obligatorio' })} className={`${inputStyle(!!errors.system_prompt)} font-mono text-xs`}/>
                     {errors.system_prompt && <p className={errorTextStyle}>{errors.system_prompt.message}</p>}
                </div>
            </div>
        </div>
        
        {/* --- Parámetros Avanzados --- */}
         <div className="pt-5 mt-5 border-t border-gray-200 dark:border-slate-700">
             <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Parámetros Avanzados (Opcional)</h3>
             <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">Sobrescribe los valores del modelo LLM base para este agente específico.</p>
             <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
                 <div>
                    <label htmlFor="temperature_override" className={labelStyle}>Temperatura</label>
                    <input id="temperature_override" type="number" step="0.1" {...register('temperature_override')} className={inputStyle(false)} />
                 </div>
                 <div>
                    <label htmlFor="max_tokens_override" className={labelStyle}>Máx. Tokens</label>
                    <input id="max_tokens_override" type="number" step="1" {...register('max_tokens_override')} className={inputStyle(false)} />
                 </div>
             </div>
        </div>
        
        {/* --- Checkbox de Activación --- */}
         <div className="pt-5 flex items-center">
          <input id="is_active" type="checkbox" {...register('is_active')} className="h-4 w-4 rounded border-gray-300 dark:border-gray-500 text-indigo-600 focus:ring-indigo-500" />
          <label htmlFor="is_active" className={`${labelStyle} ml-2 cursor-pointer`}>Activar este perfil de agente</label>
        </div>
      </div>

      {/* --- Botones de Acción --- */}
      <div className="mt-8 pt-5 border-t border-gray-200 dark:border-gray-700 flex justify-end space-x-3">
        <button type="button" onClick={onCancel} disabled={isSubmitting || isGeneratingPrompt} className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-slate-700 border border-gray-300 dark:border-slate-600 rounded-md hover:bg-gray-50 dark:hover:bg-slate-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70">
          Cancelar
        </button>
        <button type="submit" disabled={isSubmitting || isGeneratingPrompt} className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 border border-transparent rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70 disabled:cursor-not-allowed">
          {isSubmitting ? 'Guardando...' : (agent ? 'Actualizar Agente' : 'Crear Agente')}
        </button>
      </div>
    </form>
  );
};

export default VirtualAgentForm;