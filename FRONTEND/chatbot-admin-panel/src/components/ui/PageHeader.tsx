// src/components/ui/PageHeader.tsx
import React from 'react';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  children?: React.ReactNode; // Para poner botones u otros elementos a la derecha
}

const PageHeader: React.FC<PageHeaderProps> = ({ title, subtitle, children }) => {
  return (
    <div className="mb-6 md:mb-8 border-b border-gray-200 dark:border-slate-700 pb-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Lado Izquierdo: Título y Subtítulo */}
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-gray-800 dark:text-white leading-tight">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {subtitle}
            </p>
          )}
        </div>
        
        {/* Lado Derecho: Contenido extra (botones, etc.) */}
        {children && (
          <div className="flex items-center space-x-3">
            {children}
          </div>
        )}
      </div>
    </div>
  );
};

export default PageHeader;