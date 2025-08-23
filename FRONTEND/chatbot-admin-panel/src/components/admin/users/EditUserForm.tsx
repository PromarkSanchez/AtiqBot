// src/components/admin/users/EditUserForm.tsx

import React, { useEffect } from 'react';
import { useForm, type SubmitHandler, Controller } from 'react-hook-form';
import type { AppUserResponse, AppUserUpdateByAdmin, RoleResponse, AppUserLocalCreate } from '../../../services/api/schemas'; 
import { useReadAllRolesEndpointApiV1AdminRolesGet } from '../../../services/api/endpoints';

interface EditUserFormProps {
  user: AppUserResponse | null;
  onFormSubmit: (data: AppUserUpdateByAdmin | AppUserLocalCreate) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  isEditMode: boolean;
}

type FormValues = {
  username_ad: string;
  full_name: string | null;
  email: string | null;
  is_active_local: boolean;
  mfa_enabled: boolean;
  role_ids: number[];
  password?: string;
  confirm_password?: string;
};

const EditUserForm: React.FC<EditUserFormProps> = ({ user, onFormSubmit, onCancel, isSubmitting, isEditMode }) => {
  const {
    register,
    handleSubmit,
    reset,
    control,
    watch,
    formState: { errors, isDirty },
  } = useForm<FormValues>({
    defaultValues: {
      username_ad: '', full_name: '', email: '', is_active_local: true,
      mfa_enabled: false, role_ids: [], password: '', confirm_password: '',
    }
  });

  const { data: allRolesResponse, isLoading: isLoadingRoles } = useReadAllRolesEndpointApiV1AdminRolesGet({}, { query: { queryKey: ['allAdminRolesForForm'] } });
  const availableRoles: RoleResponse[] = allRolesResponse || [];

  useEffect(() => {
    if (isEditMode && user) {
      reset({
        username_ad: user.username_ad,
        full_name: user.full_name || '',
        email: user.email || '',
        is_active_local: user.is_active_local,
        mfa_enabled: user.mfa_enabled,
        role_ids: user.roles?.map(role => role.id) || [],
      });
    } else {
      reset({
        username_ad: '', full_name: '', email: '', is_active_local: true,
        mfa_enabled: false, role_ids: [], password: '', confirm_password: '',
      });
    }
  }, [user, isEditMode, reset]);


  const processSubmit: SubmitHandler<FormValues> = (data) => {
    // --- CHIVATO #1: ¿Qué datos nos da el formulario al hacer submit? ---
    console.log('[EditUserForm] PASO 1: Datos recibidos del hook de formulario:', data);

    if (isEditMode && user) {
        const payload: Partial<AppUserUpdateByAdmin> = {};
        
        if (data.full_name !== (user.full_name || '')) payload.full_name = data.full_name === '' ? null : data.full_name;
        if (data.email !== (user.email || '')) payload.email = data.email === '' ? null : data.email;
        if (data.is_active_local !== user.is_active_local) payload.is_active_local = data.is_active_local;
        if (data.mfa_enabled !== user.mfa_enabled) payload.mfa_enabled = data.mfa_enabled;

        const originalRoleIds = user.roles?.map(r => r.id).sort() || [];
        const newRoleIdsSorted = [...data.role_ids].sort();
        if (JSON.stringify(originalRoleIds) !== JSON.stringify(newRoleIdsSorted)) {
          payload.role_ids = data.role_ids;
        }

        // --- CHIVATO #2: ¿Qué payload estamos a punto de enviar? ---
        console.log('[EditUserForm] PASO 2: Payload final que se enviará a la página padre:', payload);

        if (Object.keys(payload).length > 0) {
            onFormSubmit(payload as AppUserUpdateByAdmin);
        } else {
            console.log("[EditUserForm] No se detectaron cambios, cerrando modal.");
            onCancel(); 
        }
    } else {
        const payload: AppUserLocalCreate = {
            username_ad: data.username_ad, full_name: data.full_name, email: data.email,
            is_active_local: data.is_active_local, password: data.password!, role_ids: data.role_ids,
        };
        console.log('[EditUserForm] PASO 2 (Creación): Payload final que se enviará:', payload);
        onFormSubmit(payload);
    }
  };
  
  return (
    <form onSubmit={handleSubmit(processSubmit)}>
      <div className="space-y-6">
        {/* ... tu JSX del formulario no necesita cambios ... */}
        <div>
          <label htmlFor="username_ad_input" className="block text-sm font-medium text-gray-700 dark:text-gray-300">DNI / Username</label>
          <input id="username_ad_input" type="text" {...register('username_ad', { required: 'El DNI es obligatorio.' })} disabled={isEditMode} className="mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm sm:text-sm text-gray-900 dark:text-white focus:ring-indigo-500 focus:border-indigo-500 disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:cursor-not-allowed"/>
          {errors.username_ad && <p className="mt-1 text-xs text-red-500 dark:text-red-400">{errors.username_ad.message}</p>}
        </div>
          {!isEditMode && (
          <>
            <div>
              <label htmlFor="password_input" className="block text-sm font-medium text-gray-700 dark:text-gray-300">Contraseña</label>
              <input id="password_input" type="password" {...register('password', { required: "La contraseña es obligatoria", minLength: { value: 8, message: "Debe tener al menos 8 caracteres" }})} className={`mt-1 block w-full px-3 py-2 border ${ errors.full_name ? 'border-red-500' : 'border-gray-300 dark:border-gray-600' } rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900`}/>
            </div>
            <div>
              <label htmlFor="confirm_password_input" className="block text-sm font-medium text-gray-700 dark:text-gray-300">Confirmar Contraseña</label>
              <input id="confirm_password_input" type="password" {...register('confirm_password', { required: "Debes confirmar la contraseña", validate: val => val === watch('password') || "Las contraseñas no coinciden" })} className={`mt-1 block w-full px-3 py-2 border ${ errors.full_name ? 'border-red-500' : 'border-gray-300 dark:border-gray-600' } rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900`}/>
              {errors.confirm_password && <p className="mt-1 text-xs text-red-500 dark:text-red-400">{errors.confirm_password.message}</p>}
            </div>
          </>
        )}
        
        <div>
          <label htmlFor="full_name_input" className="block text-sm font-medium text-gray-700 dark:text-gray-300"> Nombre Completo </label>
          <input id="full_name_input" type="text" {...register('full_name')} className={`mt-1 block w-full px-3 py-2 border ${ errors.full_name ? 'border-red-500' : 'border-gray-300 dark:border-gray-600' } rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900`} />
        </div>
        <div>
          <label htmlFor="email_input" className="block text-sm font-medium text-gray-700 dark:text-gray-300"> Email </label>
          <input id="email_input" type="email" {...register('email', { pattern: { value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i, message: 'Dirección de email inválida',},})} className={`mt-1 block w-full px-3 py-2 border ${ errors.email ? 'border-red-500' : 'border-gray-300 dark:border-gray-600' } rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900`} />
        </div>
        <div className="flex items-start">
          <div className="flex items-center h-5"> <input id="is_active_local_checkbox" type="checkbox" {...register('is_active_local')} className="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300 dark:border-gray-600 rounded bg-gray-50 dark:bg-gray-700 checked:bg-indigo-600" /> </div>
          <div className="ml-3 text-sm"> <label htmlFor="is_active_local_checkbox" className="font-medium text-gray-700 dark:text-gray-300"> Activo (Localmente) </label> </div>
        </div>
        <div className="flex items-start">
          <div className="flex items-center h-5"> <input id="mfa_enabled_checkbox" type="checkbox" {...register('mfa_enabled')} className="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300 dark:border-gray-600 rounded bg-gray-50 dark:bg-gray-700 checked:bg-indigo-600" /> </div>
          <div className="ml-3 text-sm"> <label htmlFor="mfa_enabled_checkbox" className="font-medium text-gray-700 dark:text-gray-300"> Autenticación de Múltiples Factores (MFA) </label> </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Roles Asignados</label>
          {isLoadingRoles ? <p>Cargando roles...</p> : ( <div className="space-y-2 p-3 border border-gray-300 dark:border-gray-600 rounded-md max-h-48 overflow-y-auto bg-white dark:bg-slate-700"><Controller name="role_ids" control={control} render={({ field }) => (<> {availableRoles.map((role) => ( <div key={role.id} className="flex items-center py-1"> <input id={`role-${role.id}`} type="checkbox" value={role.id} checked={field.value?.includes(role.id)} onChange={(e) => { const selectedRoleId = Number(e.target.value); const currentRoleIds = field.value || []; const newRoleIds = e.target.checked ? [...currentRoleIds, selectedRoleId] : currentRoleIds.filter((id) => id !== selectedRoleId); field.onChange(newRoleIds); }} className="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300 dark:border-gray-500 rounded bg-gray-100 dark:bg-gray-700 checked:bg-indigo-500 dark:checked:bg-indigo-500" /> <label htmlFor={`role-${role.id}`} className="ml-3 block text-sm text-gray-800 dark:text-gray-200 select-none"> {role.name} </label> </div> ))} </> )} /> </div> )}
        </div>
      </div>
      <div className="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700 flex justify-end space-x-3">
        <button type="button" onClick={onCancel} disabled={isSubmitting} className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-slate-700 border border-gray-300 dark:border-slate-600 rounded-md hover:bg-gray-50 dark:hover:bg-slate-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70">Cancelar</button>
        <button type="submit" disabled={isSubmitting || !isDirty} className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 border border-transparent rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70 disabled:cursor-not-allowed">
          {isSubmitting ? 'Guardando...' : 'Guardar Cambios'}
        </button>
      </div>
    </form>
  );
};

export default EditUserForm;