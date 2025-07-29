// src/components/admin/roles/RoleForm.tsx
import React, { useEffect, useState } from 'react';
import { useForm, Controller, type SubmitHandler } from 'react-hook-form';
import type { RoleUpdate, RoleResponse } from '../../../services/api/schemas';

// --- NUEVOS Hooks para obtener menús ---
import { 
    useGetAllMenuItemsApiV1AdminMenusGet,
    useGetMenusForRoleApiV1AdminRolesRoleIdMenusGet
} from '../../../services/api/endpoints';

// --- NUEVO tipo para el formulario, incluyendo los permisos de menú ---
type RoleFormValues = {
  name: string;
  description: string | null;
  // Guardaremos los IDs de los menús seleccionados
  menu_permissions: number[]; 
};

interface RoleFormProps {
  role?: RoleResponse | null;
  onFormSubmit: (data: RoleUpdate, permissions: { added: number[], removed: number[] }) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  isEditMode?: boolean;
}

const RoleForm: React.FC<RoleFormProps> = ({
  role,
  onFormSubmit,
  onCancel,
  isSubmitting,
  isEditMode = false,
}) => {
  const {
    register,
    handleSubmit,
    reset,
    control,
    formState: { errors, isDirty },
  } = useForm<RoleFormValues>({
    defaultValues: {
      name: '',
      description: '',
      menu_permissions: [],
    },
  });

  // --- LÓGICA PARA PERMISOS DE MENÚ ---

  // 1. Obtener TODOS los menús disponibles
  const { data: allMenusData, isLoading: isLoadingAllMenus } = useGetAllMenuItemsApiV1AdminMenusGet(
      { limit: 1000 }, { query: { staleTime: 300000 } }
  );
  const allMenus = allMenusData || [];

  // 2. Obtener los menús asignados a ESTE rol (si estamos editando)
  const roleId = isEditMode && role ? role.id : -1;
  const { data: assignedMenusData, isLoading: isLoadingAssignedMenus } = useGetMenusForRoleApiV1AdminRolesRoleIdMenusGet(
    roleId, { query: { enabled: isEditMode && roleId > 0 } }
  );
  
  // Guardamos los IDs iniciales para comparar al hacer submit
  const [initialMenuIds, setInitialMenuIds] = useState<Set<number>>(new Set());

  // Efecto para poblar el formulario
  useEffect(() => {
    if (isEditMode && role) {
      const assignedIds = assignedMenusData?.map(m => m.id) || [];
      reset({
        name: role.name,
        description: role.description || '',
        menu_permissions: assignedIds,
      });
      setInitialMenuIds(new Set(assignedIds));
    } else {
      reset({ name: '', description: '', menu_permissions: [] });
      setInitialMenuIds(new Set());
    }
  }, [role, isEditMode, reset, assignedMenusData]);


  const processSubmit: SubmitHandler<RoleFormValues> = (formData) => {
    const rolePayload: RoleUpdate = {};
    if (isDirty) {
      // Solo incluimos los campos del rol si han cambiado
      if (formData.name !== role?.name) rolePayload.name = formData.name;
      if (formData.description !== (role?.description || '')) rolePayload.description = formData.description;
    }

    const finalMenuIds = new Set(formData.menu_permissions);
    const added = Array.from(finalMenuIds).filter(id => !initialMenuIds.has(id));
    const removed = Array.from(initialMenuIds).filter(id => !finalMenuIds.has(id));

    onFormSubmit(rolePayload, { added, removed });
  };
  
  const isLoadingPermissions = isLoadingAllMenus || (isEditMode && isLoadingAssignedMenus);

  return (
    <form onSubmit={handleSubmit(processSubmit)}>
      <div className="space-y-6">
        {/* Campos de Nombre y Descripción (se mantienen igual) */}
        <div>
          <label htmlFor="role_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
            Nombre del Rol <span className="text-red-500">*</span>
          </label>
          <input
            id="role_name"
            type="text"
            {...register('name', { required: 'El nombre del rol es obligatorio.' })}
            className={`mt-1 block w-full px-3 py-2 border ${
              errors.name ? 'border-red-500 dark:border-red-400' : 'border-gray-300 dark:border-gray-600'
            } rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900`}
          />
          {errors.name && (
            <p className="mt-1 text-xs text-red-500 dark:text-red-400">{errors.name.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="role_description" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
            Descripción (Opcional)
          </label>
          <textarea
            id="role_description"
            rows={3}
            {...register('description')}
            className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-900"
          />
          {errors.description && (
            <p className="mt-1 text-xs text-red-500 dark:text-red-400">{errors.description.message}</p>
          )}
        </div>

        {/* --- NUEVA SECCIÓN DE PERMISOS --- */}
        {isEditMode && (
          <div>
            <hr className="my-6 border-gray-200 dark:border-slate-700"/>
            <label className="block text-base font-semibold text-gray-800 dark:text-gray-200">
              Permisos de Menú del Panel
            </label>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">Selecciona los menús a los que este rol tendrá acceso.</p>
            
            {isLoadingPermissions ? (
              <div className="p-4 text-center animate-pulse text-gray-500 dark:text-gray-400">Cargando permisos...</div>
            ) : (
              <div className="space-y-3 p-4 border border-gray-300 dark:border-slate-600 rounded-md max-h-60 overflow-y-auto bg-gray-50 dark:bg-slate-900/50">
                <Controller
                  name="menu_permissions"
                  control={control}
                  defaultValue={[]}
                  render={({ field }) => (
                    <>
                      {allMenus.map(menu => (
                        <div key={menu.id} className="flex items-center">
                          <input
                            type="checkbox"
                            id={`menu-perm-${menu.id}`}
                            value={menu.id}
                            checked={field.value?.includes(menu.id)}
                            onChange={e => {
                              const menuId = Number(e.target.value);
                              const newValues = e.target.checked
                                ? [...(field.value || []), menuId]
                                : (field.value || []).filter(id => id !== menuId);
                              field.onChange(newValues);
                            }}
                            className="h-4 w-4 rounded border-gray-300 dark:border-gray-500 text-indigo-600 focus:ring-indigo-500 bg-white dark:bg-slate-700"
                          />
                          <label htmlFor={`menu-perm-${menu.id}`} className="ml-3 block text-sm font-medium text-gray-700 dark:text-gray-300 cursor-pointer">
                            {menu.parent_id && <span className="mr-1 opacity-60">↳</span>}
                            {menu.name}
                          </label>
                        </div>
                      ))}
                    </>
                  )}
                />
              </div>
            )}
          </div>
        )}
      </div>

      <div className="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700 flex justify-end space-x-3">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-slate-700 border border-gray-300 dark:border-slate-600 rounded-md hover:bg-gray-50 dark:hover:bg-slate-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70"
        >
          Cancelar
        </button>
        <button
          type="submit"
          disabled={isSubmitting || !isDirty} // En edición y creación, se habilita al haber cambios.
          className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 border border-transparent rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-70 disabled:cursor-not-allowed"
        >
          {isSubmitting ? 'Guardando...' : (isEditMode ? 'Actualizar Rol' : 'Crear Rol')}
        </button>
      </div>
    </form>
  );
};

export default RoleForm;