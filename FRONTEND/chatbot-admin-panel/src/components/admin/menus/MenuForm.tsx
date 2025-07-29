// src/components/admin/menus/MenuForm.tsx
import React, { useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import type { SubmitHandler } from 'react-hook-form';

import type { AdminPanelMenuResponse, AdminPanelMenuCreate, AdminPanelMenuUpdate } from '../../../services/api/schemas';
import { useGetAllMenuItemsApiV1AdminMenusGet } from '../../../services/api/endpoints';

// Tipo de datos para el formulario, basado en el schema de creación.
type MenuFormDataType = Omit<AdminPanelMenuCreate, 'parent_id'> & {
    parent_id: number | null; // Usamos number | null para el select
};

interface MenuFormProps {
  menu?: AdminPanelMenuResponse | null;
  onFormSubmit: (data: AdminPanelMenuCreate | AdminPanelMenuUpdate) => void;
  onCancel: () => void;
  isSubmitting: boolean;
  isEditMode: boolean;
}

const MenuForm: React.FC<MenuFormProps> = ({
  menu,
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
    formState: { errors, isDirty },
  } = useForm<MenuFormDataType>({
    mode: 'onChange',
    defaultValues: {
      name: '',
      frontend_route: '',
      icon_name: null,
      display_order: 100,
      parent_id: null,
    },
  });

  // Cargar todos los menús para usarlos como posibles padres
  const { data: allMenus, isLoading: isLoadingMenus } = useGetAllMenuItemsApiV1AdminMenusGet(
    { limit: 1000 },
    { query: { queryKey: ['allMenusForParentSelector'], staleTime: 300000 } }
  );

  // Filtrar para que un menú no pueda ser su propio padre
  const availableParentMenus = allMenus?.filter(m => m.id !== menu?.id) || [];

  // Efecto para llenar el formulario en modo edición
  useEffect(() => {
    if (isEditMode && menu) {
      reset({
        name: menu.name || '',
        frontend_route: menu.frontend_route || '',
        icon_name: menu.icon_name || null,
        display_order: menu.display_order ?? 100,
        parent_id: menu.parent_id || null,
      });
    } else {
      reset(); // Reset a los valores por defecto para el modo creación
    }
  }, [menu, isEditMode, reset]);

  const processSubmit: SubmitHandler<MenuFormDataType> = (formData) => {
    const payload: AdminPanelMenuCreate | AdminPanelMenuUpdate = {
      name: formData.name.trim(),
      frontend_route: formData.frontend_route.trim(),
      icon_name: formData.icon_name ? formData.icon_name.trim() : null,
      // react-hook-form a veces devuelve el número como string, aseguramos que sea número
      display_order: Number(formData.display_order), 
      // Si no hay selección, parent_id será null o '', lo normalizamos a null.
      parent_id: formData.parent_id ? Number(formData.parent_id) : null,
    };
    onFormSubmit(payload);
  };
  
  // Clases Tailwind reutilizadas de tu ApiClientForm
  const labelClass = "block text-sm font-medium text-gray-700 dark:text-gray-300";
  const inputBaseClass = "mt-1 block w-full px-3 py-2 border rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-slate-800 dark:text-white disabled:bg-gray-100 dark:disabled:bg-slate-700";
  const inputNormalClass = "border-gray-300 dark:border-gray-600";
  const inputErrorClass = "border-red-500 dark:border-red-400";
  const selectClass = `${inputBaseClass} ${inputNormalClass}`;
  const btnSecondaryClass = "px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-slate-700 border border-gray-300 dark:border-slate-600 rounded-md hover:bg-gray-50 dark:hover:bg-slate-600 focus:outline-none disabled:opacity-70";
  const btnPrimaryClass = "px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 border border-transparent rounded-md shadow-sm focus:outline-none disabled:opacity-70 disabled:cursor-not-allowed";

  return (
    <form onSubmit={handleSubmit(processSubmit)}>
      <div className="space-y-6 p-1">
        {/* Grid para los campos principales */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-6">
          <div>
            <label htmlFor="menu_name" className={labelClass}>Nombre del Menú <span className="text-red-500">*</span></label>
            <input id="menu_name" type="text" 
              {...register('name', { required: 'El nombre es obligatorio.' })}
              className={`${inputBaseClass} ${errors.name ? inputErrorClass : inputNormalClass}`} />
            {errors.name && <p className="mt-1 text-xs text-red-500">{errors.name.message}</p>}
          </div>

          <div>
            <label htmlFor="menu_route" className={labelClass}>Ruta Frontend <span className="text-red-500">*</span></label>
            <input id="menu_route" type="text" 
              {...register('frontend_route', { required: 'La ruta es obligatoria.' })}
              className={`${inputBaseClass} ${errors.frontend_route ? inputErrorClass : inputNormalClass}`} 
              placeholder="/admin/nueva-pagina"/>
            {errors.frontend_route && <p className="mt-1 text-xs text-red-500">{errors.frontend_route.message}</p>}
          </div>

          <div>
            <label htmlFor="menu_icon" className={labelClass}>Nombre del Icono (Heroicons)</label>
            <input id="menu_icon" type="text" 
              {...register('icon_name')}
              className={`${inputBaseClass} ${inputNormalClass}`} 
              placeholder="Ej: Cog6ToothIcon"/>
          </div>

          <div>
            <label htmlFor="menu_order" className={labelClass}>Orden de Visualización</label>
            <input id="menu_order" type="number" 
              {...register('display_order', { valueAsNumber: true })}
              className={`${inputBaseClass} ${inputNormalClass}`} />
          </div>
        </div>
        
        {/* Selector de Menú Padre */}
        <div>
          <label htmlFor="menu_parent" className={labelClass}>Menú Padre (Opcional)</label>
          <Controller
              name="parent_id"
              control={control}
              render={({ field }) => (
                  <select
                      id="menu_parent"
                      {...field}
                      onChange={e => field.onChange(e.target.value ? Number(e.target.value) : null)}
                      value={field.value ?? ''}
                      className={selectClass}
                      disabled={isLoadingMenus}
                  >
                      <option value="">{isLoadingMenus ? 'Cargando...' : '-- Ninguno (Nivel Superior) --'}</option>
                      {availableParentMenus.map(parent => (
                          <option key={parent.id} value={parent.id}>{parent.name}</option>
                      ))}
                  </select>
              )}
          />
        </div>
      </div>

      {/* Botones de Acción */}
      <div className="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700 flex justify-end space-x-3">
        <button type="button" onClick={onCancel} disabled={isSubmitting} className={btnSecondaryClass}>Cancelar</button>
        <button type="submit" 
          disabled={isSubmitting || (!isDirty && isEditMode)} 
          className={btnPrimaryClass}>
          {isSubmitting ? 'Guardando...' : (isEditMode ? 'Guardar Cambios' : 'Crear Menú')}
        </button>
      </div>
    </form>
  );
};

export default MenuForm;