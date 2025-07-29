// src/components/layout/AdminLayout.tsx
import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar'; // Crearemos este componente
import Topbar from './Topbar';   // Crearemos este componente

const AdminLayout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen bg-gray-100 dark:bg-gray-900">
      {/* Sidebar (será dinámico para móvil/desktop) */}
      <Sidebar sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />
      
      <div className="flex flex-col flex-1 overflow-y-auto">
        {/* Topbar (incluirá el botón de hamburguesa y logout) */}
        <Topbar setSidebarOpen={setSidebarOpen} />
        
        {/* Contenido Principal de la página */}
        <main className="p-4 md:p-6 lg:p-8">
            <Outlet /> {/* Aquí se renderizan AdminUsersPage, AdminRolesPage, etc. */}
        </main>
        
        {/* Opcional: Footer si lo deseas */}
        <footer className="bg-white dark:bg-slate-800 shadow-inner mt-auto">
          <div className="max-w-full mx-auto py-3 px-4 sm:px-6 lg:px-8 text-center text-gray-500 dark:text-gray-400 text-sm">
            © {new Date().getFullYear()} Mi Chatbot Avanzado - Panel de Admin
          </div>
        </footer>
      </div>
    </div>
  );
};

export default AdminLayout;