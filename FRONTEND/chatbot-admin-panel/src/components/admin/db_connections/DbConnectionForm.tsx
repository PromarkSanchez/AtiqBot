// src/components/admin/db_connections/DbConnectionForm.tsx
import React, { useEffect } from 'react';
import { useForm, type SubmitHandler, Controller } from 'react-hook-form';
import type {
  DatabaseConnectionCreate,
  DatabaseConnectionUpdate,
  DatabaseConnectionResponse,
  DBTypeSchema,
  // DatabaseConnectionCreateExtraParams, // Si este tipo es solo 'object | null' no necesitamos importarlo explícitamente aquí
  // DatabaseConnectionUpdateExtraParams
} from '../../../services/api/schemas';
import { DBTypeSchema as DBTypeEnum } from '../../../services/api/schemas'; // Para acceder a los valores del enum
import toast from 'react-hot-toast';

type DbConnectionFormValues = {
  name: string;
  description: string; // Usaremos string vacío para el input
  db_type: DBTypeSchema;
  host: string;
  port: number | string; // string para el input, luego se convierte a number
  database_name: string;
  username: string;
  password?: string; // Solo para creación o si se quiere cambiar en edición
  extra_params_json: string;
};

interface DbConnectionFormProps {
  dbConnection?: DatabaseConnectionResponse | null;
  onFormSubmit: (data: DatabaseConnectionCreate | Partial<DatabaseConnectionUpdate>) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  isEditMode?: boolean;
}

const getExtraParamsPlaceholder = (dbType?: DBTypeSchema): string => {
  let example = {};
  switch (dbType) {
    case DBTypeEnum.POSTGRESQL:
      example = { sslmode: 'prefer', connect_timeout: 10 };
      break;
    case DBTypeEnum.SQLSERVER:
      example = { driver: 'ODBC Driver 17 for SQL Server', Encrypt: 'yes', TrustServerCertificate: 'no' };
      break;
    case DBTypeEnum.MYSQL:
      example = { charset: 'utf8mb4', connection_timeout: 10 };
      break;
    case DBTypeEnum.ORACLE:
      example = { encoding: 'UTF-8', nencoding: 'UTF-8', connect_timeout: 60 };
      break;
    default:
      example = { custom_param: "valor_ejemplo" };
  }
  return JSON.stringify(example, null, 2);
};


const DbConnectionForm: React.FC<DbConnectionFormProps> = ({
  dbConnection,
  onFormSubmit,
  onCancel,
  isSubmitting,
  isEditMode = false,
}) => {
  const {
    register,
    handleSubmit,
    reset,
    control, // Para el <select>
    watch, // Para observar db_type y actualizar placeholder de extra_params
    formState: { errors, isDirty },
    setError,
    clearErrors,
  } = useForm<DbConnectionFormValues>({
    defaultValues: {
      name: '',
      description: '',
      db_type: DBTypeEnum.POSTGRESQL, // Un valor por defecto
      host: '',
      port: '', // Empezar como string
      database_name: '',
      username: '',
      password: '',
      extra_params_json: getExtraParamsPlaceholder(DBTypeEnum.POSTGRESQL),
    },
  });

  const watchedDbType = watch('db_type');

  useEffect(() => {
    // Actualizar el placeholder de extra_params si db_type cambia y es modo creación o el campo está "vacío"
    if (!isEditMode || (isEditMode && (!dbConnection?.extra_params || dbConnection.extra_params === null || Object.keys(dbConnection.extra_params).length === 0))) {
      reset(currentValues => ({ ...currentValues, extra_params_json: getExtraParamsPlaceholder(watchedDbType) }));
    }
  }, [watchedDbType, isEditMode, dbConnection, reset]);


  useEffect(() => {
    if (dbConnection) {
      reset({
        name: dbConnection.name || '',
        description: dbConnection.description || '',
        db_type: dbConnection.db_type,
        host: dbConnection.host || '',
        port: dbConnection.port?.toString() || '',
        database_name: dbConnection.database_name || '',
        username: dbConnection.username || '',
        password: '', // La contraseña no se precarga para editar
        extra_params_json: dbConnection.extra_params ? JSON.stringify(dbConnection.extra_params, null, 2) : getExtraParamsPlaceholder(dbConnection.db_type),
      });
    } else { // Modo creación
      reset({
        name: '', description: '', db_type: DBTypeEnum.POSTGRESQL, host: '',
        port: '', database_name: '', username: '', password: '',
        extra_params_json: getExtraParamsPlaceholder(DBTypeEnum.POSTGRESQL)
      });
    }
  }, [dbConnection, reset]);

  const validateAndParseJson = (value: string): object | null | undefined => {
    try {
      const trimmedValue = value.trim();
      if (trimmedValue === "" || trimmedValue === "{}") {
        clearErrors("extra_params_json");
        return trimmedValue === "{}" ? {} : null; // Devolver objeto vacío o null
      }
      const parsed = JSON.parse(trimmedValue);
      clearErrors("extra_params_json");
      return parsed;
    } catch (e) {
      setError("extra_params_json", { type: "manual", message: "El JSON de parámetros extra no es válido." });
      return undefined; // Indicar error de validación
    }
  };

  const processFormSubmit: SubmitHandler<DbConnectionFormValues> = (formData) => {
    const parsedExtraParams = validateAndParseJson(formData.extra_params_json);
    if (parsedExtraParams === undefined && formData.extra_params_json.trim() !== "" && formData.extra_params_json.trim() !== "{}") { // Si undefined Y el string no estaba vacío
      toast.error("Por favor, corrige el JSON de Parámetros Extra.", {id: "jsonExtraParamsError"});
      return;
    }

    const portAsNumber = parseInt(formData.port as string, 10);
    if (isNaN(portAsNumber)) {
      setError("port", { type: "manual", message: "El puerto debe ser un número." });
      return;
    }

    const commonPayload = {
      name: formData.name,
      description: formData.description.trim() === '' ? null : formData.description,
      db_type: formData.db_type,
      host: formData.host,
      port: portAsNumber,
      database_name: formData.database_name,
      username: formData.username,
      extra_params: parsedExtraParams, // Puede ser object o null
    };

    if (isEditMode && dbConnection) {
      const updatePayload: Partial<DatabaseConnectionUpdate> = {};
      // Solo añadir campos si cambiaron
      if (commonPayload.name !== dbConnection.name) updatePayload.name = commonPayload.name;
      if (commonPayload.description !== (dbConnection.description || null)) updatePayload.description = commonPayload.description;
      if (commonPayload.db_type !== dbConnection.db_type) updatePayload.db_type = commonPayload.db_type;
      if (commonPayload.host !== dbConnection.host) updatePayload.host = commonPayload.host;
      if (commonPayload.port !== dbConnection.port) updatePayload.port = commonPayload.port;
      if (commonPayload.database_name !== dbConnection.database_name) updatePayload.database_name = commonPayload.database_name;
      if (commonPayload.username !== dbConnection.username) updatePayload.username = commonPayload.username;
      
      if (formData.password && formData.password.trim() !== '') { // Solo enviar contraseña si se ingresó una nueva
        updatePayload.password = formData.password;
      }

      const originalExtraParamsString = dbConnection.extra_params ? JSON.stringify(dbConnection.extra_params) : null;
      const currentExtraParamsString = parsedExtraParams ? JSON.stringify(parsedExtraParams) : null;
      if (currentExtraParamsString !== originalExtraParamsString) {
        updatePayload.extra_params = parsedExtraParams as any; // Aserción temporal para el tipo complejo de Orval
      }

      if (Object.keys(updatePayload).length > 0) {
        onFormSubmit(updatePayload);
      } else {
        toast("No se detectaron cambios.", { duration: 2000, icon: 'ℹ️' });
        onCancel();
      }
    } else { // Modo Creación
      const createPayload: DatabaseConnectionCreate = {
        ...commonPayload,
        // La contraseña es opcional en DatabaseConnectionCreate, pero si está vacía, enviar undefined/null
        password: (formData.password && formData.password.trim() !== '') ? formData.password : undefined,
        extra_params: parsedExtraParams as any, // Aserción temporal
      };
      onFormSubmit(createPayload);
    }
  };
  
  // Clases Tailwind (simplificado, define las tuyas)
  const labelClass = "block text-sm font-medium text-gray-700 dark:text-gray-300";
  const inputClass = (hasError?: boolean) => `mt-1 block w-full px-3 py-2 border rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900 ${hasError ? 'border-red-500 dark:border-red-400' : 'border-gray-300 dark:border-gray-600'}`;
  const btnSecondaryClass = "px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-slate-700 border border-gray-300 dark:border-slate-600 rounded-md hover:bg-gray-50 dark:hover:bg-slate-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70";
  const btnPrimaryClass = "px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 border border-transparent rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70 disabled:cursor-not-allowed";


  return (
    <form onSubmit={handleSubmit(processFormSubmit)}>
      <div className="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2">
        {/* Nombre */}
        <div className="sm:col-span-2">
          <label htmlFor="db_conn_name" className={labelClass}>Nombre Conexión <span className="text-red-500">*</span></label>
          <input type="text" id="db_conn_name" {...register('name', { required: 'El nombre es obligatorio.' })} className={inputClass(!!errors.name)} />
          {errors.name && <p className="mt-1 text-xs text-red-500">{errors.name.message}</p>}
        </div>

        {/* Descripción */}
        <div className="sm:col-span-2">
          <label htmlFor="db_conn_description" className={labelClass}>Descripción</label>
          <textarea id="db_conn_description" rows={2} {...register('description')} className={inputClass(!!errors.description)} />
        </div>

        {/* Tipo de BD */}
        <div>
          <label htmlFor="db_conn_db_type" className={labelClass}>Tipo de Base de Datos <span className="text-red-500">*</span></label>
          <Controller
            name="db_type"
            control={control}
            rules={{ required: "Debe seleccionar un tipo de BD" }}
            render={({ field }) => (
              <select id="db_conn_db_type" {...field} className={inputClass(!!errors.db_type)}>
                {Object.entries(DBTypeEnum).map(([key, value]) => (
                  <option key={key} value={value}>{key}</option>
                ))}
              </select>
            )}
          />
          {errors.db_type && <p className="mt-1 text-xs text-red-500">{errors.db_type.message}</p>}
        </div>

        {/* Host */}
        <div>
          <label htmlFor="db_conn_host" className={labelClass}>Host / Servidor <span className="text-red-500">*</span></label>
          <input type="text" id="db_conn_host" {...register('host', { required: 'El host es obligatorio.' })} className={inputClass(!!errors.host)} />
          {errors.host && <p className="mt-1 text-xs text-red-500">{errors.host.message}</p>}
        </div>
        
        {/* Puerto */}
        <div>
          <label htmlFor="db_conn_port" className={labelClass}>Puerto <span className="text-red-500">*</span></label>
          <input type="number" id="db_conn_port" {...register('port', { required: 'El puerto es obligatorio.', valueAsNumber: true })} className={inputClass(!!errors.port)} />
          {errors.port && <p className="mt-1 text-xs text-red-500">{errors.port.message}</p>}
        </div>

        {/* Nombre de BD */}
        <div>
          <label htmlFor="db_conn_database_name" className={labelClass}>Nombre de Base de Datos <span className="text-red-500">*</span></label>
          <input type="text" id="db_conn_database_name" {...register('database_name', { required: 'El nombre de la BD es obligatorio.' })} className={inputClass(!!errors.database_name)} />
          {errors.database_name && <p className="mt-1 text-xs text-red-500">{errors.database_name.message}</p>}
        </div>

        {/* Usuario */}
        <div>
          <label htmlFor="db_conn_username" className={labelClass}>Usuario <span className="text-red-500">*</span></label>
          <input type="text" id="db_conn_username" {...register('username', { required: 'El usuario es obligatorio.' })} className={inputClass(!!errors.username)} />
          {errors.username && <p className="mt-1 text-xs text-red-500">{errors.username.message}</p>}
        </div>

        {/* Contraseña */}
        <div>
          <label htmlFor="db_conn_password" className={labelClass}>
            Contraseña {isEditMode ? '(Dejar en blanco para no cambiar)' : <span className="text-red-500">*</span>}
          </label>
          <input type="password" id="db_conn_password" {...register('password', { required: !isEditMode })} className={inputClass(!!errors.password)} autoComplete="new-password"/>
          {errors.password && <p className="mt-1 text-xs text-red-500">{errors.password.message}</p>}
        </div>
        
        {/* Parámetros Extra JSON */}
        <div className="sm:col-span-2">
          <label htmlFor="db_conn_extra_params_json" className={labelClass}>Parámetros Extra (JSON)</label>
           <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
            (Ej. drivers, timeouts, SSL. El ejemplo se actualiza según el Tipo de BD).
          </p>
          <textarea
            id="db_conn_extra_params_json"
            rows={8}
            {...register('extra_params_json', { onBlur: (e) => validateAndParseJson(e.target.value) })}
            className={`font-mono text-xs leading-relaxed ${inputClass(!!errors.extra_params_json)}`}
          />
          {errors.extra_params_json && <p className="mt-1 text-xs text-red-500">{errors.extra_params_json.message}</p>}
        </div>
      </div>

      <div className="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700 flex justify-end space-x-3">
        <button type="button" onClick={onCancel} disabled={isSubmitting} className={btnSecondaryClass}>Cancelar</button>
        <button type="submit" disabled={isSubmitting || (isEditMode && !isDirty)} className={btnPrimaryClass}>
          {isSubmitting ? 'Guardando...' : (isEditMode ? 'Actualizar Conexión' : 'Crear Conexión')}
        </button>
      </div>
    </form>
  );
};

export default DbConnectionForm;