import React, { useEffect } from 'react';
// Importamos useWatch para reaccionar a cambios en el formulario
import { useForm, type SubmitHandler, useWatch } from 'react-hook-form';

import type { LLMModelConfigResponse, LLMModelConfigCreate } from '../../../services/api/schemas';
import { LLMProviderType, LLMModelType } from '../../../services/api/schemas';
import { KeyIcon, GlobeAltIcon, ShieldCheckIcon } from '@heroicons/react/24/outline'; // <-- Importamos un icono nuevo

const providerOptions = Object.values(LLMProviderType);
const modelTypeOptions = Object.values(LLMModelType);

type LlmModelFormValues = LLMModelConfigCreate & {
  // Añadimos un campo "falso" al tipo del formulario para la UX
  aws_region_ui?: string; 
  aws_access_key_id_ui?: string;
  aws_secret_access_key_ui?: string;
};




interface LlmModelFormProps {
  model?: LLMModelConfigResponse | null;
  onFormSubmit: (data: LLMModelConfigCreate) => void;
  onCancel: () => void;
  isSubmitting: boolean;
}

const LlmModelForm: React.FC<LlmModelFormProps> = ({ model, onFormSubmit, onCancel, isSubmitting }) => {
  const {
    register,
    handleSubmit,
    reset,
    control, // <-- Necesitamos `control` para useWatch
    formState: { errors },
  } = useForm<LlmModelFormValues>({
    defaultValues: {
      is_active: true,
      provider: LLMProviderType.GOOGLE,
      model_type: LLMModelType.CHAT_COMPLETION,
      default_temperature: 0.7,
      default_max_tokens: 2048,
      supports_system_prompt: true,
      api_key_plain: '',
      config_json: {},
      aws_region_ui: 'us-east-1', // <-- Valor por defecto para nuestro campo de UX
      aws_access_key_id_ui: '',
      aws_secret_access_key_ui: '',
    },
  });

  // Observamos el valor del campo 'provider' en tiempo real
  const selectedProvider = useWatch({
    control,
    name: 'provider',
  });

  useEffect(() => {
    if (model) {
      const awsRegion = (model.config_json as any)?.aws_region || 'us-east-1';
      const modelForForm = {
        ...model,
        api_key_plain: '', 
        config_json: model.config_json || {},
        aws_region_ui: awsRegion, // <-- Poblamos nuestro campo de UX
      };
      reset(modelForForm);
    } else {
      // Al crear, volvemos a los valores por defecto del useForm
      reset(); 
    }
  }, [model, reset]);

  // ### [CORRECCIÓN FINAL] ### Lógica de `processSubmit` ajustada para ser compatible con TypeScript estricto.
  const processSubmit: SubmitHandler<LlmModelFormValues> = (data) => {
    
    // 1. Manejar campos numéricos correctamente
    const tempValue = data.default_temperature;
    const tokensValue = data.default_max_tokens;
    
    // Si tempValue es `null` o `undefined`, se convierte en `null`. Si es un número, se mantiene.
    // Esto es seguro para TypeScript porque ya no comparamos un número con un string.
    const temperature = (tempValue === null || tempValue === undefined) ? null : Number(tempValue);
    const maxTokens = (tokensValue === null || tokensValue === undefined) ? null : Number(tokensValue);
    
    // 2. Construir el config_json dinámicamente
    //let configJson: Record<string, any> | undefined;
    const configJson: Record<string, any> = {};

    if (data.provider === LLMProviderType.BEDROCK) {
      if (data.aws_region_ui?.trim()) {
        configJson.aws_region = data.aws_region_ui.trim();
      }
      // Solo añadimos las claves si el usuario las ha escrito.
      if (data.aws_access_key_id_ui?.trim()) {
        configJson.aws_access_key_id = data.aws_access_key_id_ui.trim();
      }
      if (data.aws_secret_access_key_ui?.trim()) {
        configJson.aws_secret_access_key = data.aws_secret_access_key_ui.trim();
      }
    }

    // 3. Crear el payload final, excluyendo nuestro campo de UX `aws_region_ui`
    const finalPayload: LLMModelConfigCreate = {
      display_name: data.display_name,
      model_identifier: data.model_identifier,
      provider: data.provider,
      model_type: data.model_type,
      is_active: data.is_active,
      base_url: data.base_url?.trim() === '' ? undefined : data.base_url,
      default_temperature: temperature,
      default_max_tokens: maxTokens,
      supports_system_prompt: data.supports_system_prompt,
      api_key_plain: data.api_key_plain?.trim() === '' ? undefined : data.api_key_plain,
      config_json: Object.keys(configJson).length > 0 ? configJson : undefined,
    };
    
    onFormSubmit(finalPayload);
  };

  const isEditMode = !!model;

  return (
    <form onSubmit={handleSubmit(processSubmit)} noValidate>
      <div className="space-y-6 max-h-[70vh] overflow-y-auto p-1 pr-4">
        {/* --- Bloques existentes (Fila 1 y 2) se mantienen igual --- */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
          <div>
            <label htmlFor="display_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Nombre a Mostrar <span className="text-red-500">*</span>
            </label>
            <input id="display_name" type="text" {...register('display_name', { required: 'El nombre es obligatorio.' })} className={`mt-1 block w-full px-3 py-2 border ${errors.display_name ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900`} />
            {errors.display_name && <p className="mt-1 text-xs text-red-500">{errors.display_name.message}</p>}
          </div>
          <div>
            <label htmlFor="model_identifier" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Identificador del Modelo (API) <span className="text-red-500">*</span>
            </label>
            <input id="model_identifier" type="text" placeholder="ej: gemini-1.5-pro-latest" {...register('model_identifier', { required: 'El identificador es obligatorio.' })} className={`mt-1 block w-full px-3 py-2 border ${errors.model_identifier ? 'border-red-500' : 'border-gray-300 dark:border-gray-600'} rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900`} />
            {errors.model_identifier && <p className="mt-1 text-xs text-red-500">{errors.model_identifier.message}</p>}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
          <div>
            <label htmlFor="provider" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Proveedor <span className="text-red-500">*</span>
            </label>
            <select id="provider" {...register('provider')} className="mt-1 block w-full pl-3 pr-10 py-2 border border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md text-gray-900 dark:text-white bg-white dark:bg-gray-900">
              {providerOptions.map((prov) => (<option key={prov} value={prov}>{prov}</option>))}
            </select>
          </div>
          <div>
            <label htmlFor="model_type" className="block text-sm font-medium text-gray-700 dark:text-gray-300">Tipo de Modelo</label>
            <select id="model_type" {...register('model_type')} className="mt-1 block w-full pl-3 pr-10 py-2 border border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md text-gray-900 dark:text-white bg-white dark:bg-gray-900">
              {modelTypeOptions.map((type) => (<option key={type} value={type}>{type}</option>))}
            </select>
          </div>
        </div>
        
        {/* ### [MEJORA] ### Campos Condicionales para Proveedores Específicos */}
        
        {selectedProvider === LLMProviderType.BEDROCK && (
          <div className="p-4 rounded-md bg-indigo-50 dark:bg-slate-900/40 border border-indigo-200 dark:border-slate-700 space-y-4">
            <h3 className="text-sm font-semibold text-indigo-800 dark:text-indigo-300 mb-3 flex items-center">
              <GlobeAltIcon className="h-5 w-5 mr-2" />
              Configuración de AWS Bedrock (Opcional)
            </h3>
            <p className="text-xs text-indigo-600 dark:text-indigo-400">
              Rellena estos campos si necesitas usar credenciales específicas en lugar de las del entorno.
            </p>

            {/* CAMPO DE REGIÓN (EXISTENTE) */}
            <div>
              <label htmlFor="aws_region_ui" className="block text-sm font-medium text-gray-700 dark:text-gray-300">Región de AWS</label>
              <input id="aws_region_ui" type="text" placeholder="ej: us-east-1" {...register('aws_region_ui')} className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900" />
            </div>

            {/* NUEVO CAMPO: ACCESS KEY ID */}
            <div>
              <label htmlFor="aws_access_key_id_ui" className="block text-sm font-medium text-gray-700 dark:text-gray-300">AWS Access Key ID</label>
              <input id="aws_access_key_id_ui" type="text" autoComplete="off" placeholder="Dejar en blanco para usar rol de IAM" {...register('aws_access_key_id_ui')} className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900" />
            </div>

            {/* NUEVO CAMPO: SECRET ACCESS KEY */}
            <div>
              <label htmlFor="aws_secret_access_key_ui" className="block text-sm font-medium text-gray-700 dark:text-gray-300">AWS Secret Access Key</label>
              <input id="aws_secret_access_key_ui" type="password" autoComplete="new-password" placeholder={isEditMode ? "Dejar en blanco para no cambiar" : "Se guardará de forma segura"} {...register('aws_secret_access_key_ui')} className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900" />
            </div>
            
            {isEditMode && (model?.config_json as any)?.aws_access_key_id_encrypted && (
                <div className="flex items-center p-2 rounded-md bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800">
                    <ShieldCheckIcon className="h-5 w-5 text-green-500 mr-2 flex-shrink-0"/>
                    <span className="text-sm text-green-800 dark:text-green-300">Ya hay credenciales de AWS guardadas. Rellena los campos solo para sobreescribirlas.</span>
                </div>
            )}
          </div>
        )}
        {/* --- Bloque de API Key existente --- */}
        <hr className="my-5 border-gray-200 dark:border-slate-700"/>
        <div>
          <label htmlFor="api_key_plain" className="block text-sm font-medium text-gray-700 dark:text-gray-300">API Key</label>
          {isEditMode && model?.has_api_key && (<div className="mt-1 mb-2 flex items-center p-2 rounded-md bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800"><KeyIcon className="h-5 w-5 text-green-500 mr-2 flex-shrink-0"/><span className="text-sm text-green-800 dark:text-green-300">Ya hay una API key guardada.</span></div>)}
          <input id="api_key_plain" type="password" autoComplete="new-password" placeholder={isEditMode ? "Dejar en blanco para no cambiar" : "Pega la API Key aquí"} {...register('api_key_plain')} className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900" />
           <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{isEditMode ? "Introduce un valor solo si deseas sobreescribir la clave." : "La clave se guardará de forma segura y encriptada."}</p>
        </div>

        {/* --- Bloque URL Base existente --- */}
         <div>
          <label htmlFor="base_url" className="block text-sm font-medium text-gray-700 dark:text-gray-300">URL Base (Opcional)</label>
          <input id="base_url" type="text" placeholder="Para modelos locales (ej: http://localhost:11434)" {...register('base_url')} className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900" />
        </div>
        
        {/* --- Bloque de Parámetros existente --- */}
        <hr className="my-5 border-gray-200 dark:border-slate-700"/>
        <p className="text-base font-semibold text-gray-800 dark:text-gray-200">Parámetros por Defecto</p>
         <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
            <div>
              <label htmlFor="default_temperature" className="block text-sm font-medium text-gray-700 dark:text-gray-300">Temperatura (0.0 - 2.0)</label>
              <input id="default_temperature" type="number" step="0.1" {...register('default_temperature')} className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900" />
            </div>
             <div>
              <label htmlFor="default_max_tokens" className="block text-sm font-medium text-gray-700 dark:text-gray-300">Máximo de Tokens</label>
              <input id="default_max_tokens" type="number" step="1" {...register('default_max_tokens')} className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900" />
            </div>
        </div>
        
        {/* --- Bloque de Checkboxes existente --- */}
         <div className="flex items-start space-x-6 pt-2">
            <div className="flex items-center">
              <input id="is_active" type="checkbox" {...register('is_active')} className="h-4 w-4 rounded border-gray-300 dark:border-gray-500 text-indigo-600 focus:ring-indigo-500" />
              <label htmlFor="is_active" className="ml-2 block text-sm font-medium text-gray-700 dark:text-gray-300">Activo</label>
            </div>
             <div className="flex items-center">
              <input id="supports_system_prompt" type="checkbox" {...register('supports_system_prompt')} className="h-4 w-4 rounded border-gray-300 dark:border-gray-500 text-indigo-600 focus:ring-indigo-500" />
              <label htmlFor="supports_system_prompt" className="ml-2 block text-sm font-medium text-gray-700 dark:text-gray-300">Soporta System Prompt</label>
            </div>
        </div>
      </div>

      {/* --- Botones de Acción existentes --- */}
      <div className="mt-8 pt-5 border-t border-gray-200 dark:border-gray-700 flex justify-end space-x-3">
        <button type="button" onClick={onCancel} disabled={isSubmitting} className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-slate-700 border border-gray-300 dark:border-slate-600 rounded-md hover:bg-gray-50 dark:hover:bg-slate-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70">
          Cancelar
        </button>
        <button type="submit" disabled={isSubmitting} className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 border border-transparent rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70 disabled:cursor-not-allowed">
          {isSubmitting ? 'Guardando...' : (isEditMode ? 'Actualizar Modelo' : 'Crear Modelo')}
        </button>
      </div>
    </form>
  );
};

export default LlmModelForm;