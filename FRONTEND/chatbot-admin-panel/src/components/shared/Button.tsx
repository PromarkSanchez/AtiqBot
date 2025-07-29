// src/components/shared/Button.tsx
import React from 'react';

// --- Tipos para Button ---
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  icon?: React.ReactNode;
  children: React.ReactNode; // Texto del botón
}

// --- Componente Button ---
export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  icon,
  children,
  className = '',
  disabled,
  ...props
}) => {
  const baseStyles =
    'inline-flex items-center justify-center font-medium rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 dark:focus:ring-offset-slate-800 transition-colors duration-150 ease-in-out';

  let variantStyles = '';
  switch (variant) {
    case 'primary':
      variantStyles = 'bg-indigo-600 hover:bg-indigo-700 text-white focus:ring-indigo-500 disabled:bg-indigo-400';
      break;
    case 'secondary':
      variantStyles = 'bg-white dark:bg-slate-700 text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-slate-600 hover:bg-gray-50 dark:hover:bg-slate-600 focus:ring-indigo-500 disabled:bg-gray-100 dark:disabled:bg-slate-600';
      break;
    case 'danger':
      variantStyles = 'bg-red-600 hover:bg-red-700 text-white focus:ring-red-500 disabled:bg-red-400';
      break;
    case 'outline': // A menudo usado con color específico via className
      variantStyles = 'bg-transparent border border-current hover:bg-opacity-10 focus:ring-current';
      break;
    case 'ghost': // Sin borde, solo texto/icono coloreado
      variantStyles = 'bg-transparent hover:bg-gray-100 dark:hover:bg-slate-700 focus:ring-current disabled:text-gray-400 dark:disabled:text-slate-500';
      break;
  }

  let sizeStyles = '';
  switch (size) {
    case 'sm':
      sizeStyles = `px-3 py-1.5 text-xs ${icon && children ? 'space-x-1.5' : ''}`;
      break;
    case 'md':
      sizeStyles = `px-4 py-2 text-sm ${icon && children ? 'space-x-2' : ''}`;
      break;
    case 'lg':
      sizeStyles = `px-6 py-3 text-base ${icon && children ? 'space-x-2' : ''}`;
      break;
  }

  const spinner = (
    <svg className="animate-spin h-5 w-5 text-current" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
    </svg>
  );

  return (
    <button
      type="button" // Default a button, puede ser overridden por props
      className={`${baseStyles} ${variantStyles} ${sizeStyles} ${className} ${disabled || isLoading ? 'opacity-70 cursor-not-allowed' : ''}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && <span className="mr-2">{spinner}</span>}
      {icon && !isLoading && <span className={children ? 'mr-1.5 md:mr-2' : ''}>{icon}</span>}
      {children}
    </button>
  );
};


// --- Tipos para IconButton (similar a Button pero usualmente solo icono) ---
interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline'; // 'ghost' es común para IconButtons
  size?: 'sm' | 'md' | 'lg'; // Tamaño del área del botón, no necesariamente del icono
  icon: React.ReactNode;
  'aria-label': string; // Requerido para accesibilidad
}

// --- Componente IconButton ---
export const IconButton: React.FC<IconButtonProps> = ({
  variant = 'ghost', // Ghost suele ser un buen default
  size = 'md',
  icon,
  className = '',
  ...props
}) => {
   const baseStyles =
    'inline-flex items-center justify-center rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 dark:focus:ring-offset-slate-800 transition-colors duration-150 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed';

  let variantStyles = '';
   switch (variant) {
    case 'primary': // Generalmente los icon buttons no usan primary/secondary sólidos pero es posible
      variantStyles = 'bg-indigo-600 hover:bg-indigo-700 text-white focus:ring-indigo-500';
      break;
    case 'secondary':
      variantStyles = 'bg-white dark:bg-slate-700 text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-slate-600 hover:bg-gray-50 dark:hover:bg-slate-600 focus:ring-indigo-500';
      break;
    case 'danger':
      variantStyles = 'bg-red-100 dark:bg-red-700/30 text-red-600 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-700/50 focus:ring-red-500';
      break;
    case 'ghost': // Default
       variantStyles = 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-slate-700 focus:ring-indigo-500'; // Colores del icono y hover bg
      break;
    case 'outline':
      variantStyles = 'text-gray-500 dark:text-gray-400 border border-gray-300 dark:border-slate-600 hover:bg-gray-100 dark:hover:bg-slate-700 focus:ring-indigo-500';
      break;
  }

  let sizeStyles = '';
  switch (size) {
    case 'sm': sizeStyles = 'p-1.5'; break; // Icono h-4 w-4 o h-5 w-5 usualmente
    case 'md': sizeStyles = 'p-2'; break;   // Icono h-5 w-5 o h-6 w-6
    case 'lg': sizeStyles = 'p-2.5'; break; // Icono h-6 w-6 o h-7 w-7
  }

  return (
    <button
      type="button"
      className={`${baseStyles} ${variantStyles} ${sizeStyles} ${className}`}
      {...props}
    >
      {icon}
    </button>
  );
};