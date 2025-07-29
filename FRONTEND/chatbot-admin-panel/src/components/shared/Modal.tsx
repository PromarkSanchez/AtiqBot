// src/components/shared/Modal.tsx
import React, { useEffect, useRef, type ReactNode } from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline'; // Para el botón de cerrar

// Tamaños del modal mapeados a clases de Tailwind
type ModalSize = 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl' | '4xl' | '5xl' | 'fit';

const sizeClasses: Record<ModalSize, string> = {
  sm: 'sm:max-w-sm',
  md: 'sm:max-w-md',
  lg: 'sm:max-w-lg', // Este era tu default sm:max-w-lg
  xl: 'sm:max-w-xl',
  '2xl': 'sm:max-w-2xl',
  '3xl': 'sm:max-w-3xl',
  '4xl': 'sm:max-w-4xl',
  '5xl': 'sm:max-w-5xl',
  fit: 'sm:max-w-fit', // Para que se ajuste al contenido
};

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footerContent?: ReactNode;
  size?: ModalSize; // Nueva prop para el tamaño
  unmountOnClose?: boolean; // Opción para desmontar el contenido cuando está cerrado
  bodyClassName?: string; // Clase adicional para el div del body
  disableBackdropClick?: boolean; // Para evitar cerrar al hacer clic en el overlay
}

const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  footerContent,
  size = 'lg', // Default size
  unmountOnClose = true, // Por defecto, desmontar para limpiar estado de formularios, etc.
  bodyClassName = '',
  disableBackdropClick = false,
}) => {
  const modalRef = useRef<HTMLDivElement>(null);

  // Cerrar con tecla Escape
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      // Evitar scroll en el body de la página cuando el modal está abierto
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'auto';
    };
  }, [isOpen, onClose]);

  // Enfocar el modal para accesibilidad
  useEffect(() => {
    if (isOpen && modalRef.current) {
      modalRef.current.focus();
    }
  }, [isOpen]);

  // No renderizar nada si está cerrado y se debe desmontar
  if (unmountOnClose && !isOpen) {
    return null;
  }
  
  const handleOverlayClick = () => {
    if (!disableBackdropClick) {
      onClose();
    }
  };
  
  const handleModalContentClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // Evitar que el clic en el contenido del modal cierre el modal
  };

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center overflow-y-auto px-4 py-6 transition-all duration-300 ease-in-out 
                 ${isOpen ? 'opacity-100 visible' : 'opacity-0 invisible'} 
                 bg-black/60 dark:bg-black/70 backdrop-blur-sm`}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title-heading"
      tabIndex={-1} // Para que el div del overlay pueda ser enfocado (para el Escape)
      ref={modalRef}
    >
      {/* Contenedor del Modal */}
      <div
        className={`relative flex flex-col bg-white dark:bg-slate-800 rounded-lg shadow-xl 
                   transform transition-all duration-300 ease-in-out 
                   ${isOpen ? 'scale-100 opacity-100 translate-y-0' : 'scale-95 opacity-0 -translate-y-10'} 
                   w-full ${sizeClasses[size]} max-h-[90vh]`} // max-h para asegurar visibilidad en pantallas pequeñas
        onClick={handleModalContentClick}
        role="document" // Más apropiado para el contenido interno
      >
        {/* Encabezado del Modal */}
        <div className="flex items-center justify-between px-4 py-3 sm:px-6 border-b border-gray-200 dark:border-slate-700 shrink-0">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white" id="modal-title-heading">
            {title}
          </h3>
          <button
            onClick={onClose}
            type="button"
            className="p-1 -m-1 rounded-md text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 
                       focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-indigo-400 focus:ring-offset-2 dark:focus:ring-offset-slate-800"
            aria-label="Cerrar modal"
          >
            <XMarkIcon className="h-6 w-6" aria-hidden="true" />
          </button>
        </div>

        {/* Cuerpo del Modal (con scroll si es necesario) */}
        <div className={`flex-auto overflow-y-auto p-4 sm:p-6 ${bodyClassName}`}>
          {children}
        </div>

        {/* Pie del Modal (si se proporciona) */}
        {footerContent && (
          <div className="px-4 py-3 sm:px-6 bg-gray-50 dark:bg-slate-800/50 border-t border-gray-200 dark:border-slate-700 text-right shrink-0">
            {footerContent}
          </div>
        )}
      </div>
    </div>
  );
};

export default Modal;