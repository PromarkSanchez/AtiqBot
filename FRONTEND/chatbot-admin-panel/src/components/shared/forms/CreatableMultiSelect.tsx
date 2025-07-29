// src/components/shared/forms/CreatableMultiSelect.tsx
import { useEffect, useState, type ReactNode } from 'react';
import { Controller, type Control, type FieldPath, type FieldValues, type PathValue, type Path } from 'react-hook-form';
import RSCreatableSelect from 'react-select/creatable'; // Renombrado para evitar conflicto
import type { StylesConfig } from 'react-select';
import toast from 'react-hot-toast';

// Define la estructura de una opción que react-select espera
interface SelectOption {
  readonly label: string;
  readonly value: string; // Usaremos string para value consistentemente
}

// Props del componente
interface CreatableMultiSelectProps<TFieldValues extends FieldValues> {
  name: FieldPath<TFieldValues>;
  control: Control<TFieldValues>;
  label?: string;
  placeholder?: string;
  options?: SelectOption[]; // Opciones pre-cargadas, ahora siempre SelectOption[]
  isLoading?: boolean;
  isDisabled?: boolean; // NUEVA PROP
  id?: string;
  noOptionsMessage?: (obj: { inputValue: string }) => ReactNode; // Mensaje cuando no hay opciones
  formatCreateLabel?: (inputValue: string) => ReactNode; // Mensaje para crear nueva opción
  menuPlacement?: 'auto' | 'bottom' | 'top';
}

// --- Estilos Personalizados (más alineados con Tailwind y Dark Mode) ---
// Es mejor usar clases de Tailwind si tu proyecto lo permite masivamente,
// pero los styles directos también funcionan. Usaremos variables CSS que DEBES definir en tu CSS global.
const customStyles = (isDark: boolean): StylesConfig<SelectOption, true> => ({
  control: (provided, state) => ({
    ...provided,
    backgroundColor: isDark ? 'var(--color-slate-700, #334155)' : 'var(--color-white, #ffffff)',
    borderColor: state.isFocused 
        ? 'var(--color-indigo-500, #6366f1)' 
        : (isDark ? 'var(--color-slate-600, #475569)' : 'var(--color-gray-300, #d1d5db)'),
    boxShadow: state.isFocused ? `0 0 0 1px var(--color-indigo-500, #6366f1)` : 'none',
    borderRadius: '0.375rem', // rounded-md
    minHeight: '38px',
    fontSize: '0.875rem', // text-sm
    '&:hover': {
      borderColor: isDark ? 'var(--color-slate-500, #64748b)' : 'var(--color-gray-400, #9ca3af)',
    },
  }),
  valueContainer: (provided) => ({
    ...provided,
    padding: '2px 8px',
  }),
  multiValue: (provided) => ({
    ...provided,
    backgroundColor: isDark ? 'var(--color-indigo-600, #4f46e5)' : 'var(--color-indigo-100, #e0e7ff)',
    borderRadius: '0.25rem', // rounded-sm
  }),
  multiValueLabel: (provided) => ({
    ...provided,
    color: isDark ? 'var(--color-indigo-100, #e0e7ff)' : 'var(--color-indigo-700, #4338ca)',
    fontSize: '0.875rem', // text-sm
    paddingLeft: '0.5rem',
    paddingRight: '0.25rem',
  }),
  multiValueRemove: (provided) => ({
    ...provided,
    color: isDark ? 'var(--color-indigo-200, #c7d2fe)' : 'var(--color-indigo-500, #6366f1)',
    '&:hover': {
      backgroundColor: isDark ? 'var(--color-indigo-700, #4338ca)' : 'var(--color-indigo-200, #c7d2fe)',
      color: isDark ? 'var(--color-white, #ffffff)' : 'var(--color-indigo-700, #4338ca)',
    },
  }),
  input: (provided) => ({
    ...provided,
    color: isDark ? 'var(--color-gray-100, #f3f4f6)' : 'var(--color-gray-900, #111827)',
    margin: '0px', // Resetear margen
    paddingTop: '0px', // Resetear padding
    paddingBottom: '0px', // Resetear padding
  }),
  placeholder: (provided) => ({
    ...provided,
    color: isDark ? 'var(--color-slate-400, #94a3b8)' : 'var(--color-gray-400, #9ca3af)',
  }),
  menu: (provided) => ({
    ...provided,
    backgroundColor: isDark ? 'var(--color-slate-700, #334155)' : 'var(--color-white, #ffffff)',
    borderRadius: '0.375rem',
    boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06)', // shadow-lg
    zIndex: 50, // Asegurar que esté por encima de otros elementos
  }),
  option: (provided, state) => ({
    ...provided,
    backgroundColor: state.isSelected
      ? (isDark ? 'var(--color-indigo-600, #4f46e5)' : 'var(--color-indigo-500, #6366f1)')
      : state.isFocused
      ? (isDark ? 'var(--color-slate-600, #475569)' : 'var(--color-indigo-50, #eef2ff)')
      : 'transparent',
    color: state.isSelected
      ? 'var(--color-white, #ffffff)'
      : (isDark ? 'var(--color-gray-200, #e5e7eb)' : 'var(--color-gray-900, #111827)'),
    fontSize: '0.875rem', // text-sm
    '&:active': { // Para el clic
        backgroundColor: isDark ? 'var(--color-indigo-700, #4338ca)' : 'var(--color-indigo-600, #4f46e5)',
    },
  }),
  indicatorsContainer: (provided) => ({
    ...provided,
    height: '36px', // Ajustar altura
  }),
  clearIndicator: (provided) => ({
    ...provided,
    color: isDark ? 'var(--color-slate-400, #94a3b8)' : 'var(--color-gray-400, #9ca3af)',
    '&:hover': {
        color: isDark ? 'var(--color-slate-200, #e2e8f0)' : 'var(--color-gray-600, #4b5563)',
    }
  }),
  dropdownIndicator: (provided) => ({
    ...provided,
     color: isDark ? 'var(--color-slate-400, #94a3b8)' : 'var(--color-gray-400, #9ca3af)',
    '&:hover': {
        color: isDark ? 'var(--color-slate-200, #e2e8f0)' : 'var(--color-gray-600, #4b5563)',
    }
  })
  // ... puedes añadir más estilos para indicatorSeparator, etc.
});


const CreatableMultiSelect = <TFieldValues extends FieldValues>({
  name,
  control,
  label,
  placeholder,
  options = [], // Default a array vacío
  isLoading = false,
  isDisabled = false, // Default para isDisabled
  id,
  noOptionsMessage = () => 'No hay opciones',
  formatCreateLabel = (inputValue) => `Crear "${inputValue}"`,
  menuPlacement = 'auto',
}: CreatableMultiSelectProps<TFieldValues>) => {
  // Determinar si el modo oscuro está activo (ejemplo, puedes tener una forma más global de hacer esto)
  const [isDarkMode, setIsDarkMode] = useState(false);
  useEffect(() => {
    setIsDarkMode(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => setIsDarkMode(mediaQuery.matches);
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  return (
    <div>
      {label && (
        <label htmlFor={id || name} className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          {label}
        </label>
      )}
      <Controller
        name={name}
        control={control}
        // `defaultValue` para Controller si el campo puede ser `undefined` al inicio,
        // para que `field.value` no sea `undefined` lo que causaría error en `map`.
        // RHF v7+ debería manejar `undefined` como `[]` si `defaultValues` en `useForm` lo tiene así.
        defaultValue={[] as PathValue<TFieldValues, Path<TFieldValues>>} 
        render={({ field, fieldState: { error } }) => {
          // field.value es un array de strings (ej. ['valor1', 'valor2'])
          // react-select espera un array de objetos { label: string, value: string }
          const selectedOptions: SelectOption[] = Array.isArray(field.value)
            ? field.value.map((val: string | number) => ({ label: String(val), value: String(val) }))
            : [];

          return (
            <>
              <RSCreatableSelect
                isMulti
                {...field} // Pasa onBlur, etc.
                value={selectedOptions} // El valor transformado
                onChange={(newSelectedOptions) => {
                  // `newSelectedOptions` es Option[] o null
                  const newValues = newSelectedOptions ? newSelectedOptions.map(option => option.value) : [];
                  field.onChange(newValues); // Actualiza RHF con string[]
                }}
                onCreateOption={(inputValue) => {
                  const trimmedInput = inputValue.trim();
                  if (!trimmedInput) return; // No crear opción vacía

                  const currentValues: string[] = Array.isArray(field.value) ? field.value : [];
                  if (!currentValues.includes(trimmedInput)) { // Evitar duplicados
                    field.onChange([...currentValues, trimmedInput]);
                  } else {
                    toast(`"${trimmedInput}" ya ha sido añadido.`);
                  }
                }}
                inputId={id || name}
                options={options}
                className="react-select-container" // Para targeting CSS global
                classNamePrefix="react-select"     // Para clases internas BEM-like
                placeholder={placeholder || "Selecciona o crea opciones..."}
                isLoading={isLoading}
                isDisabled={isDisabled}
                styles={customStyles(isDarkMode)}
                noOptionsMessage={noOptionsMessage}
                formatCreateLabel={formatCreateLabel}
                menuPlacement={menuPlacement}
                // Puedes añadir más props de react-select según necesites
                // como menuIsOpen, onMenuOpen, onMenuClose, etc.
              />
              {error && <p className="mt-1 text-xs text-red-500 dark:text-red-400">{error.message}</p>}
            </>
          );
        }}
      />
    </div>
  );
};

export default CreatableMultiSelect;