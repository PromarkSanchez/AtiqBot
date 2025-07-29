// src/components/layout/AdminLayout.tsx
import React from 'react';
import { Outlet, useLocation, Navigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import { useAuth } from '../../contexts/AuthContext';

const PermissionCheck: React.FC = () => {
    const { user, hasAccessToRoute, isLoadingMenus, authorizedMenus } = useAuth();
    const location = useLocation();

    // Mientras los menús cargan, no mostramos nada para evitar un parpadeo de contenido.
    // El 'isLoading' del contexto general ya evita que esto se renderice antes de tiempo.
    if (isLoadingMenus && !user?.roles.includes('SuperAdmin')) {
        return (
            <div className="p-20 text-center text-gray-400 animate-pulse">
                Verificando...
            </div>
        );
    }
    
    // Decisión de acceso
    if (hasAccessToRoute(location.pathname)) {
        return <Outlet />; // Permiso concedido, renderiza la página
    }

    // -- Lógica de Redirección si el acceso es denegado --

    // Caso 1: El usuario no tiene ningún permiso de menú asignado.
    if (authorizedMenus.length === 0 && !user?.roles.includes('SuperAdmin')) {
        return <Navigate to="/access-denied" replace />;
    }

    // Caso 2: Intenta acceder a una página específica sin permiso, pero tiene otros menús.
    // Redirigir al primer menú seguro que tiene.
    const firstAllowedRoute = authorizedMenus.find(menu => menu.frontend_route !== '#config' && menu.frontend_route !== '#context');
    const safePath = firstAllowedRoute?.frontend_route || '/admin'; // Fallback a /admin si nada se encuentra

    return <Navigate to={safePath} replace />;
};

// Layout Principal
const AdminLayout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = React.useState(false);

  return (
    <div className="flex h-screen bg-gray-100 dark:bg-gray-900">
      <Sidebar sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />
      
      <div className="flex flex-col flex-1 overflow-y-auto">
        <Topbar setSidebarOpen={setSidebarOpen} />
        
        <main className="flex-grow p-4 md:p-6 lg:p-8">
            {/* El componente PermissionCheck ahora decide qué se renderiza aquí */}
            <PermissionCheck />
        </main>
      </div>
    </div>
  );
};

export default AdminLayout;