// src/components/admin/doc_sources/DocSourceForm.tsx
import React, { useEffect } from 'react';
import { useForm, Controller, type SubmitHandler } from 'react-hook-form';
import type {
  DocumentSourceCreate,
  DocumentSourceUpdate,
  DocumentSourceResponse,
  DocSourceType,
} from '../../../services/api/schemas';
import { DocSourceType as DocSourceTypeEnum } from '../../../services/api/schemas';

// --- Funciones Helper ---

const getPlaceholder = (sourceType: DocSourceType, field: 'path' | 'creds'): string => {
  if (field === 'path') {
    switch (sourceType) {
      case DocSourceTypeEnum.LOCAL_FOLDER:
        return "/ruta/absoluta/a/tus/documentos";
      case DocSourceTypeEnum.S3_BUCKET:
        return JSON.stringify({ bucket_name: "mi-bucket-s3", prefix: "carpeta/documentos/" }, null, 2);
      case DocSourceTypeEnum.AZURE_BLOB:
        return JSON.stringify({ container_name: "mi-contenedor-azure", connection_string_secret_name: "NOMBRE_SECRETO_AZURE_CONEXION" }, null, 2);
      case DocSourceTypeEnum.WEB_URL_SINGLE:
        return "https://ejemplo.com/pagina.html";
      default:
        return "";
    }
  } else { // field === 'creds'
    switch (sourceType) {
      case DocSourceTypeEnum.S3_BUCKET:
        return JSON.stringify({ aws_access_key_id: "TU_ACCESS_KEY_ID", aws_secret_access_key: "TuClaveSecretaAcceso..." }, null, 2);
      case DocSourceTypeEnum.AZURE_BLOB:
        return JSON.stringify({ account_name: "nombrecuentaazure", account_key_secret_name: "NOMBRE_SECRETO_ACCOUNT_KEY_AZURE" }, null, 2);
      default:
        return "{}";
    }
  }
};

const isJsonExpectedForPath = (sourceType: DocSourceType): boolean => {
  const jsonTypes: DocSourceType[] = [DocSourceTypeEnum.S3_BUCKET, DocSourceTypeEnum.AZURE_BLOB];
  return jsonTypes.includes(sourceType);
};

// --- Tipos y Props ---

type DocSourceFormValues = {
  name: string;
  description: string;
  source_type: DocSourceType;
  path_or_config_str: string;
  credentials_info_str: string;
  sync_frequency_cron: string;
  is_active: boolean;
};

interface DocSourceFormProps {
  docSource?: DocumentSourceResponse | null;
  onFormSubmit: (data: DocumentSourceCreate | DocumentSourceUpdate) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  isEditMode: boolean;
}

// --- Componente Principal ---
const DocSourceForm: React.FC<DocSourceFormProps> = ({
  docSource,
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
    setValue,
    formState: { errors },
  } = useForm<DocSourceFormValues>({
    mode: 'onBlur',
    defaultValues: {
      name: '',
      description: '',
      source_type: DocSourceTypeEnum.LOCAL_FOLDER,
      path_or_config_str: getPlaceholder(DocSourceTypeEnum.LOCAL_FOLDER, 'path'),
      credentials_info_str: getPlaceholder(DocSourceTypeEnum.LOCAL_FOLDER, 'creds'),
      sync_frequency_cron: '',
      is_active: true,
    },
  });

  const watchedSourceType = watch("source_type");

  // Efecto para poblar el formulario en modo edición o resetear para creación
  useEffect(() => {
    if (isEditMode && docSource) {
      reset({
        name: docSource.name,
        description: docSource.description || '',
        source_type: docSource.source_type,
        path_or_config_str: typeof docSource.path_or_config === 'object'
          ? JSON.stringify(docSource.path_or_config, null, 2)
          : String(docSource.path_or_config || ''),
        credentials_info_str: getPlaceholder(docSource.source_type, 'creds'),
        sync_frequency_cron: docSource.sync_frequency_cron || '',
        is_active: !!docSource.is_active, 

      });
    } else if (!isEditMode) {
      // Para creación, resetea a los valores por defecto. El siguiente useEffect se encargará de los cambios.
      reset();
    }
  }, [docSource, isEditMode, reset]);

  // Efecto para actualizar los valores/placeholders dinámicamente en modo creación
  useEffect(() => {
    // Solo se aplica en modo CREACIÓN
    if (isEditMode) return;

    // Actualiza el valor del campo del formulario para que el usuario vea el formato esperado
    setValue('path_or_config_str', getPlaceholder(watchedSourceType, 'path'), { shouldValidate: true, shouldDirty: true });
    setValue('credentials_info_str', getPlaceholder(watchedSourceType, 'creds'), { shouldValidate: true, shouldDirty: true });

  }, [watchedSourceType, isEditMode, setValue]);


  // Lógica de envío del formulario
  const processSubmit: SubmitHandler<DocSourceFormValues> = (formData) => {
    let parsedPathOrConfig: string | object;
    if (isJsonExpectedForPath(formData.source_type)) {
        parsedPathOrConfig = JSON.parse(formData.path_or_config_str);
    } else {
        parsedPathOrConfig = formData.path_or_config_str;
    }
    
    const credentialsStr = formData.credentials_info_str.trim();
    const parsedCredentials = (credentialsStr && credentialsStr !== '{}') ? JSON.parse(credentialsStr) : null;

    const payload: DocumentSourceCreate | DocumentSourceUpdate = {
      name: formData.name.trim(),
      description: formData.description.trim() || null,
      source_type: formData.source_type,
      path_or_config: parsedPathOrConfig as any,
      credentials_info: parsedCredentials,
      sync_frequency_cron: formData.sync_frequency_cron.trim() || null,
      is_active: formData.is_active, // <-- Se añade aquí

    };
    
    onFormSubmit(payload);
  };

  // Clases Tailwind
  const labelClass = "block text-sm font-medium text-gray-700 dark:text-gray-300";
  const inputBaseClass = "mt-1 block w-full px-3 py-2 border rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-slate-800 dark:text-white disabled:bg-gray-100 dark:disabled:bg-slate-700";
  const inputNormalClass = "border-gray-300 dark:border-gray-600";
  const inputErrorClass = "border-red-500 dark:border-red-400";
  const textareaJsonClass = "font-mono text-xs leading-relaxed";
  const btnSecondaryClass = "px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-slate-700 border border-gray-300 dark:border-slate-600 rounded-md hover:bg-gray-50 dark:hover:bg-slate-600 disabled:opacity-70";
  const btnPrimaryClass = "px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 border border-transparent rounded-md shadow-sm disabled:opacity-70 disabled:cursor-not-allowed";

  return (
    <form onSubmit={handleSubmit(processSubmit)}>
      <div className="space-y-6">
        <div>
          <label htmlFor="name" className={labelClass}>Nombre Fuente <span className="text-red-500">*</span></label>
          <input id="name" type="text" {...register('name', { required: 'El nombre es obligatorio.' })} className={`${inputBaseClass} ${errors.name ? inputErrorClass : inputNormalClass}`} />
          {errors.name && <p className="mt-1 text-xs text-red-500">{errors.name.message}</p>}
        </div>
        <div>
          <label htmlFor="description" className={labelClass}>Descripción</label>
          <textarea id="description" rows={2} {...register('description')} className={`${inputBaseClass} ${inputNormalClass}`} />
        </div>

        <div>
          <label htmlFor="source_type" className={labelClass}>Tipo de Fuente</label>
          <Controller name="source_type" control={control} render={({ field }) => (
            <select id="source_type" {...field} className={`${inputBaseClass} ${inputNormalClass}`}>
              {Object.values(DocSourceTypeEnum).map(value => (
                <option key={value} value={value}>{value.replace(/_/g, ' ')}</option>
              ))}
            </select>
          )} />
        </div>
                <div className="flex items-center">
            <input
              id="is_active"
              type="checkbox"
              {...register('is_active')}
              className="h-4 w-4 rounded border-gray-300 dark:border-gray-500 text-indigo-600 focus:ring-indigo-500"
            />
            <label htmlFor="is_active" className={`${labelClass} ml-3 cursor-pointer`}>
              Fuente de Datos Activa
            </label>
        </div>
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Si se desactiva, esta fuente no será usada en ninguna búsqueda del chatbot,
          incluso si está asociada a un contexto.
        </p>
        <div>
          <label htmlFor="path_or_config_str" className={labelClass}>
            {isJsonExpectedForPath(watchedSourceType) ? "Configuración (JSON)" : "Ruta / URL"} <span className="text-red-500">*</span>
          </label>
          <textarea id="path_or_config_str" rows={5}
            {...register('path_or_config_str', {
              required: 'Este campo es obligatorio.',
              validate: value => {
                if (isJsonExpectedForPath(watchedSourceType)) {
                  try { JSON.parse(value); return true; } 
                  catch (e) { return 'El JSON no es válido.'; }
                }
                return true;
              }
            })}
            className={`${inputBaseClass} ${isJsonExpectedForPath(watchedSourceType) ? textareaJsonClass : ''} ${errors.path_or_config_str ? inputErrorClass : inputNormalClass}`}
            placeholder={getPlaceholder(watchedSourceType, 'path')}
          />
          {errors.path_or_config_str && <p className="mt-1 text-xs text-red-500">{errors.path_or_config_str.message}</p>}
        </div>

        <div>
          <label htmlFor="credentials_info_str" className={labelClass}>Credenciales (JSON)</label>
          <textarea id="credentials_info_str" rows={5}
            {...register('credentials_info_str', {
              validate: value => {
                const trimmedValue = value.trim();
                if (!trimmedValue || trimmedValue === '{}') return true;
                try { JSON.parse(trimmedValue); return true; } 
                catch (e) { return 'El JSON de credenciales no es válido.'; }
              }
            })}
            className={`${inputBaseClass} ${textareaJsonClass} ${errors.credentials_info_str ? inputErrorClass : inputNormalClass}`}
            placeholder={getPlaceholder(watchedSourceType, 'creds')}
          />
          {errors.credentials_info_str && <p className="mt-1 text-xs text-red-500">{errors.credentials_info_str.message}</p>}
        </div>

        <div>
          <label htmlFor="sync_frequency_cron" className={labelClass}>Frecuencia de Sincronización (Cron)</label>
          <input id="sync_frequency_cron" type="text" {...register('sync_frequency_cron')} className={`${inputBaseClass} ${inputNormalClass}`} placeholder="Ej: 0 2 * * * (opcional)"/>
        </div>
      </div>

      <div className="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700 flex justify-end space-x-3">
        <button type="button" onClick={onCancel} disabled={isSubmitting} className={btnSecondaryClass}>Cancelar</button>
        <button type="submit" disabled={isSubmitting} className={btnPrimaryClass}>
          {isSubmitting ? 'Guardando...' : (isEditMode ? 'Guardar Cambios' : 'Crear Fuente')}
        </button>
      </div>
    </form>
  );
};

export default DocSourceForm;