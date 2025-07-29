// src/components/layout/Topbar.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Bars3Icon, ArrowRightOnRectangleIcon } from '@heroicons/react/24/outline';

interface TopbarProps {
  setSidebarOpen: (open: boolean) => void;
}

const Topbar: React.FC<TopbarProps> = ({ setSidebarOpen }) => {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };
  
  return (
    <header className="sticky top-0 bg-white dark:bg-slate-800 shadow-md z-10">
      <div className="px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Botón de hamburguesa para móvil (se muestra solo en pantallas pequeñas) */}
          <div className="lg:hidden">
            <button
              onClick={() => setSidebarOpen(true)}
              className="p-2 rounded-md text-gray-500 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-700"
              aria-label="Abrir menú"
            >
              <Bars3Icon className="h-6 w-6" />
            </button>
          </div>

          {/* Espaciador para centrar el título si fuera necesario, o dejarlo vacío */}
          <div className="flex-1"></div>
          
          {/* Botón de Logout */}
          <div className="flex items-center">
            <button
              onClick={handleLogout}
              className="flex items-center p-2 rounded-md text-gray-500 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-700"
              title="Cerrar Sesión"
            >
              <ArrowRightOnRectangleIcon className="h-6 w-6" />
              <span className="hidden sm:inline ml-2">Cerrar Sesión</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Topbar;